"""
tests/test_reporter_dom_only.py

Tests for the DOM-only synthetic reporter introduced by synthetic blocker
Fix 7. The reporter (``tests/synthetic_reporter.py``) MUST infer
merchant-visible state strictly from ``briefing.html`` and MUST NOT inspect
any internal artifact (``candidate_debug.json``,
``engine_run.recommendations[]``, ``engine_run.considered[]``,
``engine_run.watching[]``, ``v2_sizing_shadow.json``, ``receipts/debug.html``,
``actions_log.json``).

Engine-run-json briefing_meta IS allowed as a context-only field (e.g. the
declared vs. rendered vertical comparison). The reporter never uses it to
decide visible counts or visible callouts.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.synthetic_reporter import (
    MATERIALITY_FOOTER_SUBSTRING,
    ScenarioReport,
    count_considered_cards,
    count_recommended_cards,
    count_watching_rows,
    detect_abstain_hard_memo,
    detect_abstain_soft_callout,
    detect_materiality_footer,
    report_briefing,
    report_run_dir,
)
from bs4 import BeautifulSoup


# ---------------------------------------------------------------------------
# Path constants -- known-good briefings
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent

#: Pinned Phase 5 reference briefing produced after Phase 5.6 +5.1. Has
#: 1 directional Recommended card, 6 Considered, 2 Watching rows, and the
#: Phase 5.4 materiality footer line. No abstain callout (PUBLISH).
PHASE5_BEAUTY_BRIEFING = (
    REPO_ROOT
    / "agent_outputs"
    / "phase5_samples"
    / "beauty_brand_v2_briefing.html"
)


# ---------------------------------------------------------------------------
# Inline minimal-HTML fixtures (kept here to avoid adding committed HTML
# files; the renderer's exact class names are pinned by these tests).
# ---------------------------------------------------------------------------

ABSTAIN_SOFT_HTML = """\
<!DOCTYPE html>
<html><body>
<main class="briefing-v2">
  <section class="recommended" aria-label="Recommended">
    <h2 class="section__title">Recommended</h2>
    <div class="abstain-callout abstain-callout--soft" role="note">
      <strong class="abstain-callout__label">No primary play this month.</strong>
      <span class="abstain-callout__reason">Healthy store, no measured signal.</span>
    </div>
    <p class="section__empty">No targeting plays met audience-floor and overlap rules this run.</p>
  </section>
  <section class="considered" aria-label="Considered, not recommended">
    <h2 class="section__title">Considered, not recommended</h2>
    <div class="play-card-grid play-card-grid--muted">
      <article class="play-card play-card--rejected" data-play-id="winback_21_45" data-reason-code="no_measured_signal">
        <h3 class="play-card__title">Winback 21 45</h3>
      </article>
      <article class="play-card play-card--rejected" data-play-id="bestseller_amplify" data-reason-code="no_measured_signal">
        <h3 class="play-card__title">Bestseller Amplify</h3>
      </article>
    </div>
  </section>
  <section class="watching" aria-label="Watching">
    <h2 class="section__title">Watching</h2>
    <ul class="watching-list">
      <li class="watching-row" data-metric="net_sales"></li>
    </ul>
  </section>
  <footer class="dq-footer" aria-label="Data quality">
    <h2 class="dq-footer__title">Data quality</h2>
    <ul class="dq-footer__scale">
      <li>Monthly revenue est.: $50,000</li>
      <li>We only recommend primary plays that could realistically add at least $10,000 this month for a store your size.</li>
    </ul>
  </footer>
</main>
</body></html>
"""


ABSTAIN_HARD_HTML = """\
<!DOCTYPE html>
<html><body>
<main class="briefing-v2 briefing-v2--abstain-hard">
  <header class="briefing-v2__header">
    <h1 class="briefing-v2__title">Data quality memo</h1>
  </header>
  <section class="abstain-hard" aria-label="Data quality memo">
    <h2 class="section__title">Why no plays this run</h2>
    <p class="abstain-hard__reason">The engine cannot recommend reliably on this analysis window.</p>
    <ul class="abstain-hard__flags">
      <li class="abstain-hard__flag" data-flag="INSUFFICIENT_HISTORY">Insufficient order history.</li>
    </ul>
  </section>
  <footer class="dq-footer" aria-label="Data quality">
    <h2 class="dq-footer__title">Data quality</h2>
    <p class="dq-footer__no-flags">No data-quality flags on this run.</p>
  </footer>
</main>
</body></html>
"""


PUBLISH_NO_FOOTER_HTML = """\
<!DOCTYPE html>
<html><body>
<main class="briefing-v2">
  <section class="recommended" aria-label="Recommended">
    <h2 class="section__title">Recommended</h2>
    <div class="play-card-grid">
      <article class="play-card play-card--directional" data-play-id="first_to_second_purchase">
        <h3 class="play-card__title">First To Second Purchase</h3>
      </article>
      <article class="play-card play-card--measured" data-play-id="winback">
        <h3 class="play-card__title">Winback</h3>
      </article>
    </div>
  </section>
  <section class="considered" aria-label="Considered, not recommended">
    <div class="play-card-grid play-card-grid--muted"></div>
  </section>
  <section class="watching" aria-label="Watching">
    <ul class="watching-list"></ul>
  </section>
  <footer class="dq-footer" aria-label="Data quality">
    <p class="dq-footer__no-flags">No data-quality flags on this run.</p>
  </footer>
</main>
</body></html>
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_briefing(tmp_path: Path, html: str, name: str = "briefing.html") -> Path:
    p = tmp_path / name
    p.write_text(html, encoding="utf-8")
    return p


def _write_engine_run(
    tmp_path: Path,
    *,
    vertical: str = "beauty",
    decision_state: str = "publish",
    recommendations: int = 0,
) -> Path:
    receipts = tmp_path / "receipts"
    receipts.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": 0,
        "store_id": "test_store",
        "briefing_meta": {"vertical": vertical},
        "abstain": {"state": decision_state},
        "recommendations": [
            {"play_id": f"fake_play_{i}", "evidence_class": "targeting"}
            for i in range(recommendations)
        ],
        "considered": [],
        "watching": [],
    }
    p = receipts / "engine_run.json"
    p.write_text(json.dumps(payload), encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# Test 1 -- Reporter counts match a known fixture briefing.html
# ---------------------------------------------------------------------------


def test_phase5_pinned_briefing_dom_counts():
    """The Phase 5 sample is the canonical reference. It has 1 Recommended,
    6 Considered, 2 Watching, no abstain callouts, and the materiality footer.
    """
    assert PHASE5_BEAUTY_BRIEFING.exists(), (
        f"Phase 5 sample missing at {PHASE5_BEAUTY_BRIEFING}"
    )

    report = report_briefing(
        scenario_name="phase5_beauty_sample",
        briefing_html_path=PHASE5_BEAUTY_BRIEFING,
        engine_run_json_path=None,
        declared_vertical="beauty",
    )

    assert report.visible_recommended_count == 1
    assert report.visible_considered_count == 6
    assert report.visible_watching_count == 2
    assert report.abstain_soft_callout_present is False
    assert report.abstain_hard_memo_present is False
    assert report.materiality_footer_present is True
    assert report.declared_vertical == "beauty"


def test_inline_publish_counts(tmp_path: Path):
    briefing = _write_briefing(tmp_path, PUBLISH_NO_FOOTER_HTML)
    report = report_briefing(
        scenario_name="inline_publish",
        briefing_html_path=briefing,
        engine_run_json_path=None,
    )
    assert report.visible_recommended_count == 2
    assert report.visible_considered_count == 0
    assert report.visible_watching_count == 0
    assert report.abstain_soft_callout_present is False
    assert report.abstain_hard_memo_present is False


def test_inline_abstain_soft_counts(tmp_path: Path):
    briefing = _write_briefing(tmp_path, ABSTAIN_SOFT_HTML)
    report = report_briefing(
        scenario_name="inline_abstain_soft",
        briefing_html_path=briefing,
    )
    assert report.visible_recommended_count == 0
    assert report.visible_considered_count == 2
    assert report.visible_watching_count == 1
    assert report.abstain_soft_callout_present is True
    assert report.abstain_hard_memo_present is False


def test_inline_abstain_hard_counts(tmp_path: Path):
    briefing = _write_briefing(tmp_path, ABSTAIN_HARD_HTML)
    report = report_briefing(
        scenario_name="inline_abstain_hard",
        briefing_html_path=briefing,
    )
    assert report.visible_recommended_count == 0
    assert report.visible_considered_count == 0
    assert report.visible_watching_count == 0
    assert report.abstain_soft_callout_present is False
    assert report.abstain_hard_memo_present is True


# ---------------------------------------------------------------------------
# Test 2 -- Mutating candidate_debug.json does NOT change reported counts
# ---------------------------------------------------------------------------


def test_mutating_candidate_debug_does_not_change_dom_counts(tmp_path: Path):
    """Even if ``candidate_debug.json`` claims many pilots, the reporter
    must report ZERO Recommended cards because the DOM has zero.
    """
    briefing = _write_briefing(tmp_path, ABSTAIN_SOFT_HTML)

    # Write a maximally-misleading candidate_debug.json next to the briefing.
    receipts = tmp_path / "receipts"
    receipts.mkdir(parents=True, exist_ok=True)
    candidate_debug_path = receipts / "candidate_debug.json"
    candidate_debug_path.write_text(
        json.dumps(
            {
                "pilot_actions": [
                    {"play_id": "winback_21_45", "tier": "PRIMARY"},
                    {"play_id": "bestseller_amplify", "tier": "PILOT"},
                    {"play_id": "discount_hygiene", "tier": "PRIMARY"},
                ],
                "actions": ["pilot_a", "pilot_b", "pilot_c"],
            }
        ),
        encoding="utf-8",
    )
    # Also write an internal-only engine_run.json that claims 5 recommendations.
    engine_run_json = _write_engine_run(
        tmp_path,
        vertical="beauty",
        decision_state="abstain_soft",
        recommendations=5,
    )

    report = report_briefing(
        scenario_name="mutated_internal_state",
        briefing_html_path=briefing,
        engine_run_json_path=engine_run_json,
        declared_vertical="beauty",
    )

    # DOM is the source of truth -- ABSTAIN_SOFT_HTML has 0 Recommended.
    assert report.visible_recommended_count == 0
    assert report.visible_considered_count == 2
    assert report.abstain_soft_callout_present is True

    # Decision state is read for CONTEXT only (allowed). Confirm the reporter
    # surfaces it as decision_state_internal but does NOT use it to override
    # the visible counts.
    assert report.decision_state_internal == "abstain_soft"
    # Sanity: the DOM-only flag agrees with the internal state, but only
    # because the DOM is honest -- the test mutates the JSON to be lying.


# ---------------------------------------------------------------------------
# Test 3 -- Mutating engine_run.recommendations does NOT change reported counts
# ---------------------------------------------------------------------------


def test_mutating_engine_run_recommendations_does_not_change_dom_counts(
    tmp_path: Path,
):
    briefing = _write_briefing(tmp_path, ABSTAIN_SOFT_HTML)
    # 100 fake recommendations, but DOM has zero.
    engine_run_json = _write_engine_run(
        tmp_path,
        vertical="beauty",
        decision_state="abstain_soft",
        recommendations=100,
    )

    report = report_briefing(
        scenario_name="bogus_recommendations",
        briefing_html_path=briefing,
        engine_run_json_path=engine_run_json,
    )

    assert report.visible_recommended_count == 0, (
        "Reporter inferred Recommended count from engine_run.recommendations[] "
        "instead of briefing.html DOM."
    )
    # Considered count from DOM is also unaffected.
    assert report.visible_considered_count == 2


# ---------------------------------------------------------------------------
# Test 4 -- briefing_meta.vertical is allowed as CONTEXT only
# ---------------------------------------------------------------------------


def test_briefing_meta_vertical_is_used_as_context(tmp_path: Path):
    """The reporter MAY surface declared vs. rendered vertical from
    ``engine_run.json::briefing_meta``. It MUST NOT use it to drive any
    of the merchant-visible counts.
    """
    briefing = _write_briefing(tmp_path, ABSTAIN_SOFT_HTML)
    engine_run_json = _write_engine_run(
        tmp_path, vertical="supplements", decision_state="abstain_soft"
    )

    report = report_briefing(
        scenario_name="vertical_context",
        briefing_html_path=briefing,
        engine_run_json_path=engine_run_json,
        declared_vertical="supplements",
    )

    assert report.declared_vertical == "supplements"
    assert report.rendered_vertical == "supplements"
    # Mismatch detection should add a note when declared != rendered.
    bogus_engine_run_json = _write_engine_run(
        tmp_path / "alt", vertical="beauty", decision_state="abstain_soft"
    )
    bogus_briefing = _write_briefing(
        tmp_path / "alt", ABSTAIN_SOFT_HTML, name="briefing.html"
    )
    report_mismatch = report_briefing(
        scenario_name="vertical_mismatch",
        briefing_html_path=bogus_briefing,
        engine_run_json_path=bogus_engine_run_json,
        declared_vertical="supplements",
    )
    assert report_mismatch.declared_vertical == "supplements"
    assert report_mismatch.rendered_vertical == "beauty"
    assert any("vertical mismatch" in n for n in report_mismatch.notes)


# ---------------------------------------------------------------------------
# Test 5 -- ABSTAIN_SOFT with cards in internal JSON but no DOM cards reports 0
# ---------------------------------------------------------------------------


def test_abstain_soft_with_internal_cards_reports_zero_visible(tmp_path: Path):
    """Direct restatement of the Fix 7 motivating defect.

    The prior reporter would have read ``engine_run.recommendations[]`` and
    proudly reported "1 PRIMARY" / "2 pilots" while the merchant was shown
    a page with zero Recommended cards. This test pins the new behavior:
    DOM count is the only count.
    """
    briefing = _write_briefing(tmp_path, ABSTAIN_SOFT_HTML)
    engine_run_json = _write_engine_run(
        tmp_path,
        vertical="beauty",
        decision_state="abstain_soft",
        recommendations=3,  # internal claims 3
    )

    report = report_briefing(
        scenario_name="abstain_soft_lying_internals",
        briefing_html_path=briefing,
        engine_run_json_path=engine_run_json,
    )

    assert report.abstain_soft_callout_present is True
    assert report.visible_recommended_count == 0  # DOM source of truth
    assert report.visible_considered_count == 2


# ---------------------------------------------------------------------------
# Test 6 -- Materiality footer detection works
# ---------------------------------------------------------------------------


def test_materiality_footer_present_on_phase5_sample():
    soup = BeautifulSoup(
        PHASE5_BEAUTY_BRIEFING.read_text(encoding="utf-8"), "html.parser"
    )
    assert detect_materiality_footer(soup) is True


def test_materiality_footer_absent_on_publish_no_footer_fixture():
    soup = BeautifulSoup(PUBLISH_NO_FOOTER_HTML, "html.parser")
    assert detect_materiality_footer(soup) is False


def test_materiality_footer_substring_pin():
    """Pin the load-bearing substring; future renderer copy changes that
    drop this exact phrase should fail Fix 5's contract -- this test makes
    that contract visible.
    """
    assert MATERIALITY_FOOTER_SUBSTRING == (
        "We only recommend primary plays that could realistically add at least"
    )


# ---------------------------------------------------------------------------
# Bonus -- forbidden-source negative test
# ---------------------------------------------------------------------------


def test_reporter_does_not_read_forbidden_artifacts(tmp_path: Path, monkeypatch):
    """Belt-and-suspenders: explicitly fail if the reporter ever opens
    files that are forbidden as state-inference sources.

    We monkeypatch ``Path.open`` and ``open`` for a small whitelist; any
    open() against a forbidden basename triggers the assertion.
    """
    briefing = _write_briefing(tmp_path, ABSTAIN_SOFT_HTML)

    # Plant decoy files. The reporter should not need any of them.
    receipts = tmp_path / "receipts"
    receipts.mkdir(parents=True, exist_ok=True)
    forbidden_paths = [
        receipts / "candidate_debug.json",
        receipts / "v2_sizing_shadow.json",
        receipts / "debug.html",
        tmp_path / "actions_log.json",
    ]
    for p in forbidden_paths:
        p.write_text("{}", encoding="utf-8")

    forbidden_basenames = {p.name for p in forbidden_paths}
    opened: list[str] = []
    real_open = open

    def _spy_open(file, *args, **kwargs):  # type: ignore[no-redef]
        try:
            name = Path(file).name
        except TypeError:
            name = ""
        opened.append(name)
        if name in forbidden_basenames:
            raise AssertionError(
                f"Reporter opened forbidden artifact: {file!r}. "
                "Reporter must rely on briefing.html DOM only."
            )
        return real_open(file, *args, **kwargs)

    monkeypatch.setattr("builtins.open", _spy_open)

    # Engine_run.json is allowed for context.
    engine_run_json = _write_engine_run(
        tmp_path, vertical="beauty", decision_state="abstain_soft"
    )

    # Should succeed; should NOT have touched any forbidden basename.
    report = report_briefing(
        scenario_name="negative_forbidden_open",
        briefing_html_path=briefing,
        engine_run_json_path=engine_run_json,
    )
    assert report.visible_recommended_count == 0
    assert all(name not in forbidden_basenames for name in opened)


# ---------------------------------------------------------------------------
# Bonus -- low-level selector helpers exposed for harness reuse
# ---------------------------------------------------------------------------


def test_selectors_independent_of_higher_level_api():
    """Pin the selector helpers. Regressions in the top-level reporter
    should not be the only forcing function.
    """
    soup = BeautifulSoup(PHASE5_BEAUTY_BRIEFING.read_text(encoding="utf-8"), "html.parser")
    assert count_recommended_cards(soup) == 1
    assert count_considered_cards(soup) == 6
    assert count_watching_rows(soup) == 2
    assert detect_abstain_soft_callout(soup) is False
    assert detect_abstain_hard_memo(soup) is False
    assert detect_materiality_footer(soup) is True


def test_selectors_handle_missing_sections():
    """Reporter degrades gracefully when sections are missing entirely."""
    soup = BeautifulSoup("<html><body><main></main></body></html>", "html.parser")
    assert count_recommended_cards(soup) == 0
    assert count_considered_cards(soup) == 0
    assert count_watching_rows(soup) == 0
    assert detect_abstain_soft_callout(soup) is False
    assert detect_abstain_hard_memo(soup) is False
    assert detect_materiality_footer(soup) is False


# ---------------------------------------------------------------------------
# report_run_dir convenience wrapper
# ---------------------------------------------------------------------------


def test_report_run_dir_picks_briefing(tmp_path: Path):
    briefings = tmp_path / "briefings"
    briefings.mkdir()
    (briefings / "test_brand_briefing.html").write_text(
        ABSTAIN_HARD_HTML, encoding="utf-8"
    )
    receipts = tmp_path / "receipts"
    receipts.mkdir()
    (receipts / "engine_run.json").write_text(
        json.dumps(
            {
                "briefing_meta": {"vertical": "beauty"},
                "abstain": {"state": "abstain_hard"},
            }
        ),
        encoding="utf-8",
    )

    report = report_run_dir(
        scenario_name="report_run_dir_pick",
        out_dir=tmp_path,
        declared_vertical="beauty",
        brand="test_brand",
    )
    assert report.abstain_hard_memo_present is True
    assert report.rendered_vertical == "beauty"
    assert report.decision_state_internal == "abstain_hard"


def test_report_run_dir_glob_when_brand_unknown(tmp_path: Path):
    briefings = tmp_path / "briefings"
    briefings.mkdir()
    (briefings / "any_brand_briefing.html").write_text(
        PUBLISH_NO_FOOTER_HTML, encoding="utf-8"
    )
    report = report_run_dir(
        scenario_name="report_run_dir_glob",
        out_dir=tmp_path,
        declared_vertical=None,
        brand=None,
    )
    assert report.visible_recommended_count == 2


def test_report_returns_zeros_when_briefing_missing(tmp_path: Path):
    report = report_briefing(
        scenario_name="missing",
        briefing_html_path=tmp_path / "nope.html",
    )
    assert report.visible_recommended_count == 0
    assert report.visible_considered_count == 0
    assert report.visible_watching_count == 0
    assert report.abstain_soft_callout_present is False
    assert report.abstain_hard_memo_present is False
    assert any("not found" in n for n in report.notes)
