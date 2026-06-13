"""Phase 6A Ticket A1 — Watching cap reduction + load-bearing prioritization.

Pins two contracts on the V2 Watching section:

1. Renderer cap is 4 (single source of truth via
   :data:`src.storytelling_v2.MAX_WATCHING_RENDERED`). Synthesizing 7
   :class:`WatchedSignal` entries renders only 4 ``li.watching-row`` rows.
2. ``small_store_240d`` synthetic fixture surfaces at least one Watching
   row whose metric is in the load-bearing set
   (``returning_customer_share``, ``net_sales``,
   ``repeat_rate_within_window``, ``aov``) when any such metric is
   computable.

Phase 5.3 watching ordering is preserved: load-bearing metrics still
surface first; non-load-bearing flat metrics are still excluded; ANOMALOUS
observations still belong to the data-quality footer; MOVED non-load-bearing
observations still belong to the state-of-store paragraph.
"""
from __future__ import annotations

from pathlib import Path
import shutil
import tempfile

import pytest

from src.decide import _LOAD_BEARING_WATCH_METRICS, build_watching
from src.engine_run import (
    Observation,
    ObservationClassification,
    WatchedSignal,
)
from src.storytelling_v2 import MAX_WATCHING_RENDERED, render_watching_section

# The four load-bearing metrics named explicitly in the Phase 6A Ticket A1
# brief. ``orders`` is internally treated as load-bearing too, but the
# brief does not list it; this set is intentionally the brief's set
# (``aov`` is added on top of the contract-final spec because Phase 5.3
# already treats it as a primary-window state metric).
LOAD_BEARING_METRICS_TICKET_A1: frozenset[str] = frozenset(
    {"returning_customer_share", "net_sales", "repeat_rate_within_window", "aov"}
)


# ---------------------------------------------------------------------------
# Renderer cap is 4 — single source of truth
# ---------------------------------------------------------------------------


def test_max_watching_rendered_constant_is_four():
    """The renderer-side cap constant exists and is 4."""
    assert MAX_WATCHING_RENDERED == 4


def test_watching_section_caps_at_four_with_seven_signals():
    """Synthesize 7 WatchedSignals; renderer slices to 4 rows."""
    signals = [
        WatchedSignal(
            metric=f"metric_{i}",
            trend="up",
            threshold_to_act=f"threshold_{i}",
        )
        for i in range(7)
    ]
    html = render_watching_section(signals)
    rendered_rows = html.count('<li class="watching-row"')
    assert rendered_rows == 4, (
        f"Expected exactly 4 rendered watching rows for 7 input signals; "
        f"got {rendered_rows}. Cap source of truth is "
        "src.storytelling_v2.MAX_WATCHING_RENDERED."
    )


# ---------------------------------------------------------------------------
# Load-bearing prioritization on build_watching
# ---------------------------------------------------------------------------


def test_build_watching_prefers_load_bearing_metrics_under_cap():
    """When more than 4 candidates exist, load-bearing metrics surface
    first. This is the prioritization pin Ticket A1 requires."""

    # Six small-magnitude held movers: 2 are non-load-bearing, 4 are
    # load-bearing. All have similar magnitudes so the prior magnitude-
    # only sort would have mixed them; load-bearing prioritization must
    # promote the four named metrics ahead of the non-load-bearing two.
    obs = []
    # Non-load-bearing metrics with slightly LARGER magnitudes (so a
    # pure magnitude sort would surface them first).
    for i in range(2):
        obs.append(
            Observation(
                supporting_metric=f"misc_metric_{i}",
                change_magnitude=0.10,
                classification=ObservationClassification.HELD,
            )
        )
    # Load-bearing metrics with slightly smaller magnitudes.
    for metric in (
        "returning_customer_share",
        "net_sales",
        "repeat_rate_within_window",
        "aov",
    ):
        obs.append(
            Observation(
                supporting_metric=metric,
                change_magnitude=0.02,
                classification=ObservationClassification.HELD,
            )
        )

    watching = build_watching(obs)
    # Cap is 4.
    assert len(watching) <= 4
    # All 4 surfaced rows are load-bearing.
    surfaced_metrics = {sig.metric for sig in watching}
    assert surfaced_metrics.issubset(_LOAD_BEARING_WATCH_METRICS), (
        f"Expected only load-bearing metrics under cap; got {surfaced_metrics}"
    )
    # And in particular, the ticket-named four are all present.
    assert surfaced_metrics == LOAD_BEARING_METRICS_TICKET_A1


def test_build_watching_load_bearing_priority_does_not_break_phase5_3():
    """Phase 5.3 'flat load-bearing surfaces as stable, watching' still
    holds. A single flat returning-customer-share is still emitted."""
    obs = [
        Observation(
            supporting_metric="returning_customer_share",
            change_magnitude=0.0,
            classification=ObservationClassification.HELD,
        ),
    ]
    watching = build_watching(obs)
    assert len(watching) == 1
    assert watching[0].metric == "returning_customer_share"
    assert watching[0].trend == "flat"


# ---------------------------------------------------------------------------
# small_store_240d end-to-end — at least one load-bearing row
# ---------------------------------------------------------------------------


def _has_synthetic_fixture() -> bool:
    """Return True iff the small_store_240d synthetic CSV exists locally."""
    from tests.synthetic_harness import orders_csv_for_scenario

    return orders_csv_for_scenario("small_store_240d").exists()


@pytest.mark.skipif(
    not _has_synthetic_fixture(),
    reason="restored at S13.6-T1a (Pivot 2 strip regex cleanup)",
)
def test_small_store_240d_renders_at_least_one_load_bearing_watching_row():
    """End-to-end pin: on small_store_240d, at least one Watching row
    must surface, and that row's metric must be in the brief's
    load-bearing set."""

    from bs4 import BeautifulSoup

    from tests.synthetic_harness import (
        load_scenarios,
        run_scenario,
        vertical_for_scenario,
    )

    scenarios = load_scenarios()
    declared = vertical_for_scenario(scenarios["small_store_240d"])

    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "scen_a1_small_store"
        out.mkdir(parents=True, exist_ok=True)
        result = run_scenario("small_store_240d", out, scenarios=scenarios)
        assert result.returncode == 0, (
            f"small_store_240d run failed (rc={result.returncode}). "
            f"stderr tail: {result.stderr[-500:]}"
        )

        briefing_html = (
            out / "briefings" / "small_store_240d_briefing.html"
        )
        assert briefing_html.exists(), (
            f"small_store_240d briefing.html missing at {briefing_html}"
        )
        soup = BeautifulSoup(briefing_html.read_text(encoding="utf-8"), "html.parser")
        watching_rows = soup.select("section.watching ul.watching-list li.watching-row")
        # The single source of truth cap.
        assert len(watching_rows) <= MAX_WATCHING_RENDERED

        assert len(watching_rows) >= 1, (
            "Expected at least one Watching row on small_store_240d "
            "(load-bearing metrics are computable on this fixture). "
            "Phase 6A Ticket A1 acceptance: when any load-bearing metric "
            "is computable, at least one must surface."
        )

        surfaced_metrics = {
            (li.get("data-metric") or "").strip().lower()
            for li in watching_rows
        }
        intersection = surfaced_metrics & LOAD_BEARING_METRICS_TICKET_A1
        assert intersection, (
            f"Expected at least one Watching row whose metric is in "
            f"{sorted(LOAD_BEARING_METRICS_TICKET_A1)}; rendered metrics "
            f"were {sorted(surfaced_metrics)}."
        )

        # And the declared vertical still propagates (Fix 6 invariant);
        # a soft sanity check so a regression on this fixture is debuggable.
        assert result.declared_vertical == declared
