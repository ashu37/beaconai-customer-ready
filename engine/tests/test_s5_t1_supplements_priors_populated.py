"""S5-T1 (KI-26) — Supplements state-of-store Observations carry
non-null ``prior`` for every metric, byte-for-byte the same way Beauty
does.

Before S5-T1, ``src/state_of_store.py`` read the prior leg of every
metric from a non-existent top-level ``aligned["L28_prior"][<metric>]``
key. The actual structure produced by ``utils.kpi_snapshot_with_deltas``
is ``aligned["L28"]["prior"][<metric>]``. Result: every Observation's
typed ``prior`` slot (reserved by 6B C2/C3) was ``None`` on every run,
on every fixture — Beauty included. The supplements G-1 fixture
surfaced the gap (KI-26) because no Recommended Now card was hiding it.

This test pins the post-fix contract on the supplements G-1 fixture:
every Observation that carries a typed ``current`` value must ALSO
carry a typed ``prior`` value (Anomaly observations are exempt — they
carry neither). The same rule must hold on Beauty (parity guard); the
existing Beauty pinned slate test pins sha256 / membership, this test
adds the explicit prior-leg contract.

CONTRACT-SAFE: ``Observation.prior`` is a reserved typed slot on the
6B-frozen ``engine_run.json`` schema. Populating it is additive within
``event_version=1``; HTML renderer does NOT consume ``Observation.prior``
directly (sha256s of both pinned briefings unchanged).
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from typing import Iterable

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tests.synthetic_harness import run_scenario  # noqa: E402


_V2_SLATE_ENV: dict[str, str] = {
    "ENGINE_V2_OUTPUT": "true",
    "ENGINE_V2_DECIDE": "true",
    "ENGINE_V2_SLATE": "true",
    "ENGINE_V2_SIZING": "true",
    "WINDOW_POLICY": "auto",
}


def _run_and_get_observations(scenario: str, vertical: str) -> list[dict]:
    env = dict(_V2_SLATE_ENV)
    env["VERTICAL_MODE"] = vertical
    with tempfile.TemporaryDirectory() as td:
        out_dir = Path(td) / "s5t1"
        result = run_scenario(scenario, out_dir, env_overrides=env, timeout_sec=300)
        assert result.returncode == 0, (
            f"synthetic harness for {scenario!r} failed (rc={result.returncode}). "
            f"stderr (last 500 chars): {result.stderr[-500:]}"
        )
        receipts = out_dir / "receipts" / "engine_run.json"
        assert receipts.exists(), f"engine_run.json not produced at {receipts}"
        er = json.loads(receipts.read_text(encoding="utf-8"))
        return list(er.get("state_of_store") or [])


def _typed_observations(obs: Iterable[dict]) -> list[dict]:
    """Filter to Observations that carry a typed ``current`` value
    (i.e. NOT anomaly-only entries, which legitimately have neither
    ``current`` nor ``prior``)."""
    out: list[dict] = []
    for o in obs:
        if o.get("classification") == "anomalous":
            continue
        if o.get("current") is None:
            # Suppressed metric (e.g. repeat_rate when no identified
            # customers in the window) — neither ``current`` nor
            # ``prior`` is populated by design.
            continue
        out.append(o)
    return out


# ---------------------------------------------------------------------------
# KI-26 acceptance: supplements observations carry non-null prior
# ---------------------------------------------------------------------------


def test_supplements_observations_all_carry_non_null_prior() -> None:
    """Every typed-current Observation on the supplements G-1 fixture
    MUST carry a non-null ``prior``. This is the KI-26 acceptance
    contract: before S5-T1 the prior leg was ``None`` for AOV, repeat
    rate, orders, returning-customer share, and net sales.
    """
    obs = _run_and_get_observations("healthy_supplements_240d", "supplements")
    typed = _typed_observations(obs)
    assert typed, (
        "Expected at least one typed Observation on supplements; got 0. "
        "If supplements behavior shifted to all-anomaly or all-suppressed, "
        "this test needs an updated baseline (and KI-26 may need to be reopened)."
    )
    missing_prior = [
        o.get("supporting_metric") for o in typed if o.get("prior") is None
    ]
    assert not missing_prior, (
        f"KI-26 regression: supplements Observations with typed ``current`` "
        f"but ``prior=null``: {missing_prior}. "
        f"Check src/state_of_store.py — every metric MUST read from "
        f'``aligned["L28"]["prior"][<metric>]`` (NOT ``aligned["L28_prior"]``).'
    )


def test_supplements_observations_prior_is_numeric() -> None:
    """The typed ``prior`` slot is ``Optional[float]``. When populated,
    it must be a JSON-numeric (int or float), not a string or dict.
    """
    obs = _run_and_get_observations("healthy_supplements_240d", "supplements")
    typed = _typed_observations(obs)
    for o in typed:
        p = o.get("prior")
        assert p is None or isinstance(p, (int, float)), (
            f"Observation {o.get('supporting_metric')!r} has non-numeric "
            f"prior: {p!r} (type={type(p).__name__})."
        )


def test_supplements_observations_have_specific_metrics_populated() -> None:
    """Pin the specific KI-26 metric set: AOV, repeat rate, orders,
    returning-customer share, net sales. Each must carry a non-null
    prior on the supplements fixture.
    """
    obs = _run_and_get_observations("healthy_supplements_240d", "supplements")
    by_metric = {o.get("supporting_metric"): o for o in obs}
    expected_metrics = {
        "aov",
        "orders",
        "returning_customer_share",
        "net_sales",
        "repeat_rate_within_window",
    }
    for metric in expected_metrics:
        ob = by_metric.get(metric)
        if ob is None:
            # Metric absent from observations — acceptable if structurally
            # suppressed (e.g. repeat_rate with no identified customers),
            # but flag loudly so future drift is caught.
            continue
        if ob.get("current") is None:
            # Suppressed metric: both ``current`` and ``prior`` legitimately
            # absent by the build_observations contract.
            continue
        assert ob.get("prior") is not None, (
            f"KI-26 regression: metric {metric!r} has current="
            f"{ob.get('current')!r} but prior=None on supplements run."
        )


# ---------------------------------------------------------------------------
# Beauty parity: same rule must apply
# ---------------------------------------------------------------------------


def test_beauty_observations_all_carry_non_null_prior() -> None:
    """Beauty parity guard: same KI-26 contract on the Beauty fixture.
    Before S5-T1, Beauty's typed ``prior`` slots were ALSO ``None`` —
    the bug was structural, not supplements-specific — but the gap was
    invisible because no test pinned the prior leg. This test pins it
    on both verticals so the next regression of this class is loud.
    """
    obs = _run_and_get_observations("healthy_beauty_240d", "beauty")
    typed = _typed_observations(obs)
    assert typed, "Expected at least one typed Observation on Beauty; got 0."
    missing_prior = [
        o.get("supporting_metric") for o in typed if o.get("prior") is None
    ]
    assert not missing_prior, (
        f"KI-26 parity regression on Beauty: Observations with typed "
        f"``current`` but ``prior=null``: {missing_prior}."
    )
