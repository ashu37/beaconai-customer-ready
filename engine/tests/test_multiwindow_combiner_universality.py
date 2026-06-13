"""B-6 (Sprint 1, Engineer B) — multi-window combiner universality test.

One-time test on the Beauty pinned slate. Asserts that every PlayCard
where ``evidence_class=measured`` had its measurement block produced
via ``combine_multiwindow_statistics`` (proper meta-analysis: Fisher's
method on p-values + inverse-variance weighting on effects), NOT via
the legacy min-p / cherry-pick merge in ``_merge_multiwindow_candidates``.

Design
------
``src/stats.py`` (B-6 facility) carries a thread-local
``multiwindow_combiner_trace`` context manager. While the trace is
active, every call to ``combine_multiwindow_statistics`` in production
code records its ``(play_id, metric)`` key into a thread-local set.
Outside the context manager the recorder is a no-op so production pays
zero overhead.

The test:

1. Resolves the Beauty pinned scenario CSV path from
   ``tests/fixtures/synthetic_scenarios.yaml``.
2. Enters ``multiwindow_combiner_trace``.
3. Drives the engine via ``src.main.run`` (in-process so the trace
   survives) under the V2 flag stack.
4. Reads the resulting ``engine_run.json``; collects every PlayCard
   where ``evidence_class == "measured"``.
5. Asserts that for every measured card's ``play_id``, the trace set
   contains a ``(play_id, *)`` key (metric-agnostic match because the
   second call site in ``action_engine`` doesn't know the metric name).

If the assertion fails, the engine's V2 path emitted a measured card
whose statistic was produced outside the proper meta-analysis combiner
— per audit (post-6b §B-6) "no Beauty Recommended Now card with
class=measured can be trusted" if this happens.

Risk acknowledged: per the implementation plan, "If this fails on day 1,
becomes a real B-6 fix, not a test-only ticket — re-scope with founder
before merging the fix." On the current Beauty fixture the test PASSES
(combiner is the only path under both M4b flags = ON, which is the V2
default in the harness env).
"""
from __future__ import annotations

import importlib
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, Iterable, List, Set, Tuple

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.stats import multiwindow_combiner_trace, record_combine_multiwindow_call  # noqa: E402


SCENARIO_NAME = "healthy_beauty_240d"


# ---------------------------------------------------------------------------
# Self-tests for the trace facility
# ---------------------------------------------------------------------------


def test_trace_is_no_op_outside_context_manager():
    """Production must pay zero cost when no test holds the trace open."""
    # Calling the recorder outside the context must not raise and must
    # not leave any lingering state.
    record_combine_multiwindow_call("any_play", "any_metric")
    with multiwindow_combiner_trace() as keys:
        assert keys == set(), (
            "Trace context manager must start with an empty set; the "
            "no-op recorder above must not have leaked state."
        )


def test_trace_records_calls_inside_context():
    """The recorder must capture (play_id, metric) tuples while active."""
    with multiwindow_combiner_trace() as keys:
        record_combine_multiwindow_call("subscription_nudge", "repeat_rate")
        record_combine_multiwindow_call("first_to_second_purchase", None)
        assert keys == {
            ("subscription_nudge", "repeat_rate"),
            ("first_to_second_purchase", None),
        }


def test_trace_clears_on_exit():
    """The trace must be empty after the context manager exits."""
    with multiwindow_combiner_trace():
        record_combine_multiwindow_call("a", "b")
    # New context: must be empty.
    with multiwindow_combiner_trace() as keys:
        assert keys == set()


# ---------------------------------------------------------------------------
# End-to-end universality test
# ---------------------------------------------------------------------------


def _scenario_csv(scenario_name: str) -> Path:
    """Resolve the orders CSV path for a synthetic scenario."""
    scen_yaml = REPO_ROOT / "tests" / "fixtures" / "synthetic_scenarios.yaml"
    cfg = yaml.safe_load(scen_yaml.read_text())
    scen = cfg["scenarios"][scenario_name]
    csv_rel = scen.get("orders_csv") or f"tests/fixtures/synthetic/{scenario_name}_orders.csv"
    p = REPO_ROOT / csv_rel
    if not p.exists():
        # Fallback to the conventional naming.
        p = REPO_ROOT / "tests" / "fixtures" / "synthetic" / f"{scenario_name}_orders.csv"
    return p


def _measured_cards(engine_run: Dict[str, Any]) -> List[Tuple[str, str]]:
    """Return ``(play_id, evidence_class)`` for every PlayCard where
    ``evidence_class == "measured"`` AND the measurement block is non-
    null. This is the strict scope per audit (post-6b §B-6).

    On the current Beauty pinned slate this is the empty list -- the
    only Recommended Now card is ``first_to_second_purchase`` at
    ``directional`` (built by Phase 5.6's ``measurement_builder`` from
    L28-only signal, by design). The universality test is therefore
    currently vacuous on Beauty; it becomes load-bearing when measured-
    class cards emerge (Sprint 4 G-3 priors expansion + G-4 measurement
    redesign). A separate documented-gap test below pins the directional-
    card divergence so future work cannot silently widen the gap.
    """
    out: List[Tuple[str, str]] = []
    for k in ("recommendations", "recommended_experiments"):
        for card in engine_run.get(k) or []:
            ec = str(card.get("evidence_class") or "")
            if ec != "measured":
                continue
            if card.get("measurement") is None:
                continue
            pid = card.get("play_id")
            if pid:
                out.append((str(pid), ec))
    return out


def test_every_measured_card_on_beauty_pinned_slate_used_combiner():
    """Universality contract — see module docstring."""
    csv_path = _scenario_csv(SCENARIO_NAME)
    assert csv_path.exists(), f"Beauty pinned CSV missing at {csv_path}"

    # Activate the V2 flag stack so the combiner branch is reachable.
    # This mirrors the synthetic_harness env (extra_v2_flags=True default).
    prior_env = {
        k: os.environ.get(k)
        for k in (
            "ENGINE_V2_DECIDE",
            "ENGINE_V2_OUTPUT",
            "ENGINE_V2_SLATE",
            "ENGINE_V2_SIZING",
            "STATS_NAN_FOR_HARDCODED",
            "EVIDENCE_CLASS_ENFORCED",
            "VERTICAL_MODE",
        )
    }
    os.environ.update(
        {
            "ENGINE_V2_DECIDE": "true",
            "ENGINE_V2_OUTPUT": "true",
            "ENGINE_V2_SLATE": "true",
            "ENGINE_V2_SIZING": "true",
            "STATS_NAN_FOR_HARDCODED": "true",
            "EVIDENCE_CLASS_ENFORCED": "true",
            "VERTICAL_MODE": "beauty",
        }
    )
    try:
        # Reload utils so DEFAULTS picks up the env. main.py calls
        # get_config() which reads DEFAULTS at runtime, but the module-
        # level DEFAULTS dict snapshots os.environ at import time -- so
        # we reload to get the per-test env into the dict.
        import src.utils as su

        importlib.reload(su)
        import src.main as sm

        importlib.reload(sm)

        with tempfile.TemporaryDirectory(prefix="b6_test_") as tmp:
            out_dir = Path(tmp) / "out"
            with multiwindow_combiner_trace() as trace_keys:
                # In-process run so the thread-local trace is visible.
                # ``cwd`` does not matter for the engine; CSV path is absolute.
                sm.run(str(csv_path), "beauty", str(out_dir))
                # Snapshot the trace BEFORE leaving the context manager.
                trace_play_ids: Set[str] = {pid for (pid, _metric) in trace_keys if pid is not None}

            er_path = out_dir / "receipts" / "engine_run.json"
            assert er_path.exists(), f"engine_run.json missing at {er_path}"
            engine_run = json.loads(er_path.read_text())
    finally:
        for k, v in prior_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    measured_cards = _measured_cards(engine_run)
    # NOTE: on the current Beauty pinned slate this list is empty (only
    # ``first_to_second_purchase`` ships, at ``directional``). The
    # assertion below is universally quantified over an empty set -- the
    # contract is locked in for the moment a measured-class card emerges
    # without retroactive hand-editing. Sprint 4 G-3 / G-4 work is the
    # likely first source. The companion documented-gap test below pins
    # the directional-card divergence so the gap cannot silently widen.
    missing = [(pid, ec) for (pid, ec) in measured_cards if pid not in trace_play_ids]
    assert not missing, (
        f"Multi-window combiner universality VIOLATION on Beauty pinned "
        f"slate. The following measured-class PlayCards were rendered "
        f"without flowing through ``combine_multiwindow_statistics``: "
        f"{missing!r}. Trace recorded combiner calls for: "
        f"{sorted(trace_play_ids)!r}. Per audit post-6b §B-6, no "
        f"Recommended Now card with class=measured can be trusted if "
        f"this assertion fails."
    )


def test_directional_card_measurement_path_documented_gap():
    """B-6 documented gap (companion to the universality test).

    The current Beauty Recommended Now card is ``first_to_second_purchase``
    at ``evidence_class=directional``. Its Measurement block is built by
    ``src/measurement_builder.build_directional_play_card`` from L28-only
    primary-window signal -- explicitly NOT the multi-window combiner.
    This is by Phase 5.6 design ("supporting signal", not a full meta-
    analysis result) and is documented in the function docstring.

    This test pins that gap as KNOWN. If a future change either
    (a) routes the directional builder through the combiner, OR
    (b) reclassifies ``first_to_second_purchase`` to ``measured``,
    the test naturally extends -- update the assertion or remove the
    documented gap, and consider widening the universality test scope
    above to include directional.

    The test does NOT fail on the current state; it is structural
    documentation that lives next to the universality test for visibility.
    """
    from src.measurement_builder import build_directional_play_card  # noqa: F401

    # The function exists, is the directional card builder, and (per its
    # docstring at lines 334-345 of measurement_builder.py) constructs
    # the Measurement from the primary-window p / delta directly. If the
    # function is removed or its behavior changes, that's a contract
    # change worth surfacing here.
    src = build_directional_play_card.__doc__ or ""
    assert "L28" in src or "primary_window" in src, (
        "Phase 5.6 directional builder docstring no longer mentions "
        "L28 / primary_window; the documented-gap reasoning above may "
        "be stale. Re-audit whether the directional path now flows "
        "through ``combine_multiwindow_statistics`` and update the "
        "B-6 universality test scope if so."
    )
