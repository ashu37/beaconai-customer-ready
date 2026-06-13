"""Phase 6B Ticket C4 — Never-empty Watching copy fallback.

Tests the three conditions that gate the fallback row:
1. decision_state is PUBLISH or ABSTAIN_SOFT
2. store has >=180 days of clean history
   (proxy: cold_start=False AND INSUFFICIENT_CLEAN_HISTORY not in data_quality_flags)
3. at least one state_of_store Observation with a non-zero directional delta

When all three hold, a single ``<li class="watching-row watching-row--fallback">``
is rendered inside the Watching section instead of the empty-section paragraph.

When any condition fails, the existing ``<p class="section__empty">`` text is
rendered unchanged — cold-start, ABSTAIN_HARD, or stores with insufficient
history must behave exactly as today.

Design decision documented in the C4 summary:
- EngineRun carries no numeric history-days field.
  ``cold_start=False`` + absence of ``INSUFFICIENT_CLEAN_HISTORY`` flag is the
  correct proxy for >=180 days of clean history on this schema.
"""
from __future__ import annotations

import os
from typing import List, Optional

import pytest

from src.engine_run import (
    Abstain,
    DataQualityFlag,
    DataWindow,
    DecisionState,
    EngineRun,
    Observation,
    ObservationClassification,
    Scale,
    WatchedSignal,
)
from src.storytelling_v2 import render_engine_run

# ---------------------------------------------------------------------------
# Environment overrides — must match the V2 flag set used by the B6 fixture
# ---------------------------------------------------------------------------

_V2_ENV_OVERRIDES = {
    "ENGINE_V2_OUTPUT": "true",
    "ENGINE_V2_DECIDE": "true",
    "ENGINE_V2_SLATE": "true",
    "VERTICAL_MODE": "beauty",
}


def _apply_env(monkeypatch, overrides: dict) -> None:
    for k, v in overrides.items():
        monkeypatch.setenv(k, v)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_DIRECTIONAL_OBS = Observation(
    supporting_metric="aov",
    change_magnitude=0.04,
    classification=ObservationClassification.MOVED,
)

_ZERO_OBS = Observation(
    supporting_metric="repeat_rate",
    change_magnitude=0.0,
    classification=ObservationClassification.HELD,
)

_NULL_MAG_OBS = Observation(
    supporting_metric="revenue",
    change_magnitude=None,
    classification=ObservationClassification.HELD,
)


def _make_engine_run(
    *,
    cold_start: bool = False,
    data_quality_flags: Optional[List[DataQualityFlag]] = None,
    abstain_state: DecisionState = DecisionState.PUBLISH,
    state_of_store: Optional[List[Observation]] = None,
    watching: Optional[List[WatchedSignal]] = None,
) -> EngineRun:
    return EngineRun(
        store_id="c4_test",
        anchor_date="2026-04-30T00:00:00",
        data_window=DataWindow(primary_window="L28", available_windows=["L7", "L28", "L56", "L90"]),
        cold_start=cold_start,
        data_quality_flags=list(data_quality_flags or []),
        abstain=Abstain(state=abstain_state),
        state_of_store=list(state_of_store or []),
        watching=list(watching or []),
        scale=Scale(monthly_revenue=180_000.0, materiality_floor=5_400.0),
    )


def _watching_section(html: str) -> str:
    """Extract the Watching <section> HTML."""
    start = html.find('<section class="watching"')
    if start < 0:
        return ""
    end = html.find("</section>", start)
    return html[start : end + len("</section>")]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestFallbackFiresOnMatureStoreWithEmptyWatching:
    """test_fallback_fires_on_240d_with_empty_watching"""

    def test_fallback_fires_on_240d_with_empty_watching(self, monkeypatch) -> None:
        """Synthetic 240d store, empty watching, >=1 directional observation,
        decision_state PUBLISH — assert exactly one watching-row--fallback li
        appears and no section__empty paragraph appears.
        """
        _apply_env(monkeypatch, _V2_ENV_OVERRIDES)
        run = _make_engine_run(
            cold_start=False,
            data_quality_flags=[],
            abstain_state=DecisionState.PUBLISH,
            state_of_store=[_DIRECTIONAL_OBS],
            watching=[],
        )
        html = render_engine_run(run)
        section = _watching_section(html)

        assert section, "Watching section must be present"
        assert 'watching-row--fallback' in section, (
            "Expected watching-row--fallback fallback row to appear for 240d store"
            " with empty watching and a directional observation"
        )
        assert section.count('watching-row--fallback') == 1, (
            "Expected exactly one watching-row--fallback li"
        )
        assert 'section__empty' not in section, (
            "section__empty must NOT appear when fallback row fires"
        )

    def test_fallback_fires_under_abstain_soft(self, monkeypatch) -> None:
        """ABSTAIN_SOFT + empty watching + directional obs + sufficient history
        should also trigger the fallback row.
        """
        _apply_env(monkeypatch, _V2_ENV_OVERRIDES)
        run = _make_engine_run(
            cold_start=False,
            data_quality_flags=[],
            abstain_state=DecisionState.ABSTAIN_SOFT,
            state_of_store=[_DIRECTIONAL_OBS],
            watching=[],
        )
        html = render_engine_run(run)
        section = _watching_section(html)

        assert 'watching-row--fallback' in section, (
            "Expected fallback row under ABSTAIN_SOFT with empty watching"
        )


class TestFallbackDoesNotFireOnColdStart:
    """test_fallback_does_not_fire_on_cold_start"""

    def test_fallback_does_not_fire_on_cold_start(self, monkeypatch) -> None:
        """45d store (cold_start=True), empty watching — assert section__empty
        renders and no fallback row appears.
        """
        _apply_env(monkeypatch, _V2_ENV_OVERRIDES)
        run = _make_engine_run(
            cold_start=True,
            data_quality_flags=[],
            abstain_state=DecisionState.PUBLISH,
            state_of_store=[_DIRECTIONAL_OBS],
            watching=[],
        )
        html = render_engine_run(run)
        section = _watching_section(html)

        assert 'section__empty' in section, (
            "Cold-start store must render section__empty, not the fallback row"
        )
        assert 'watching-row--fallback' not in section, (
            "Fallback row must NOT appear for cold-start stores"
        )

    def test_fallback_does_not_fire_with_insufficient_history_flag(self, monkeypatch) -> None:
        """Store with INSUFFICIENT_CLEAN_HISTORY flag (not cold_start but flagged)
        must render section__empty, not the fallback row.
        """
        _apply_env(monkeypatch, _V2_ENV_OVERRIDES)
        run = _make_engine_run(
            cold_start=False,
            data_quality_flags=[DataQualityFlag.INSUFFICIENT_CLEAN_HISTORY],
            abstain_state=DecisionState.PUBLISH,
            state_of_store=[_DIRECTIONAL_OBS],
            watching=[],
        )
        html = render_engine_run(run)
        section = _watching_section(html)

        assert 'section__empty' in section, (
            "Store with INSUFFICIENT_CLEAN_HISTORY must render section__empty"
        )
        assert 'watching-row--fallback' not in section, (
            "Fallback row must NOT appear when INSUFFICIENT_CLEAN_HISTORY flag is set"
        )

    def test_fallback_does_not_fire_without_directional_observation(self, monkeypatch) -> None:
        """Mature store but no directional observation — fallback must NOT fire."""
        _apply_env(monkeypatch, _V2_ENV_OVERRIDES)
        run = _make_engine_run(
            cold_start=False,
            data_quality_flags=[],
            abstain_state=DecisionState.PUBLISH,
            state_of_store=[_ZERO_OBS, _NULL_MAG_OBS],
            watching=[],
        )
        html = render_engine_run(run)
        section = _watching_section(html)

        assert 'section__empty' in section, (
            "Without a directional observation, section__empty must render"
        )
        assert 'watching-row--fallback' not in section

    def test_fallback_does_not_fire_with_empty_state_of_store(self, monkeypatch) -> None:
        """Mature store but empty state_of_store — no directional obs, fallback must not fire."""
        _apply_env(monkeypatch, _V2_ENV_OVERRIDES)
        run = _make_engine_run(
            cold_start=False,
            data_quality_flags=[],
            abstain_state=DecisionState.PUBLISH,
            state_of_store=[],
            watching=[],
        )
        html = render_engine_run(run)
        section = _watching_section(html)

        assert 'section__empty' in section
        assert 'watching-row--fallback' not in section


class TestFallbackDoesNotFireWhenWatchingHasRows:
    """test_fallback_does_not_fire_when_watching_has_rows"""

    def test_fallback_does_not_fire_when_watching_has_rows(self, monkeypatch) -> None:
        """Non-empty watching — assert no watching-row--fallback in output.
        The standard watching rows must render normally.
        """
        _apply_env(monkeypatch, _V2_ENV_OVERRIDES)
        run = _make_engine_run(
            cold_start=False,
            data_quality_flags=[],
            abstain_state=DecisionState.PUBLISH,
            state_of_store=[_DIRECTIONAL_OBS],
            watching=[
                WatchedSignal(
                    metric="aov",
                    current=58.0,
                    prior=55.6,
                    trend="up",
                    threshold_to_act="AOV moves +5% sustained 2 windows",
                )
            ],
        )
        html = render_engine_run(run)
        section = _watching_section(html)

        assert 'watching-row--fallback' not in section, (
            "Fallback row must NOT appear when watching list is non-empty"
        )
        assert 'watching-row' in section, (
            "Standard watching row must render when watching list is non-empty"
        )
        assert 'section__empty' not in section


class TestFallbackCopyContent:
    """Verify the exact copy text of the fallback row."""

    def test_fallback_row_copy_is_correct(self, monkeypatch) -> None:
        """The fallback row must contain the exact approved copy text."""
        _apply_env(monkeypatch, _V2_ENV_OVERRIDES)
        run = _make_engine_run(
            cold_start=False,
            data_quality_flags=[],
            abstain_state=DecisionState.PUBLISH,
            state_of_store=[_DIRECTIONAL_OBS],
            watching=[],
        )
        html = render_engine_run(run)

        expected_fragment = (
            "Trend signals are firming up; we&#x27;ll surface specific watch items here"
            " as your run-over-run history accumulates."
        )
        # Also accept unescaped apostrophe form in case _esc renders differently
        expected_unescaped = (
            "Trend signals are firming up; we'll surface specific watch items here"
            " as your run-over-run history accumulates."
        )
        assert expected_fragment in html or expected_unescaped in html, (
            f"Fallback copy text not found in HTML output.\n"
            f"Expected one of:\n  {expected_fragment!r}\n  {expected_unescaped!r}"
        )
