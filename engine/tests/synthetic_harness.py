"""
tests/synthetic_harness.py

Synthetic scenario harness for the BeaconAI Action Engine.

Purpose
-------
A small, isolated test utility that runs a single synthetic scenario through
``python -m src.main`` and (optionally) verifies that the engine actually ran
under the scenario's declared vertical.

This module exists to fix synthetic-blocker Fix 6: prior to this fix the
matrix was being driven by ad-hoc shell loops that did not propagate
``VERTICAL_MODE`` per scenario. As a result every scenario - including
``supplement_replenishment_240d`` - ran as ``beauty`` (the default the engine
falls back to in some legacy code paths), invalidating any vertical-specific
scenario testing.

Where vertical is declared
--------------------------
``tests/fixtures/synthetic_scenarios.yaml`` declares a per-scenario
``category`` field (e.g. ``"beauty"``, ``"supplement"``, ``"lifestyle"``).
That YAML field is the canonical scenario-level vertical declaration. The
engine itself reads ``VERTICAL_MODE`` from ``cfg`` / env, with the accepted
values ``beauty`` | ``supplements`` | ``mixed`` (see ``src.utils.VERTICAL_CONFIG``
and ``src.utils.get_vertical_mode``).

The harness maps the YAML ``category`` value to the engine's ``VERTICAL_MODE``
via :func:`vertical_for_scenario`. The mapping is intentionally explicit and
small; if a scenario does not declare ``category``, the harness defaults to
``"beauty"`` (documented; see :data:`DEFAULT_VERTICAL`). This default is
deliberate, conservative, and matches the historical pre-Fix-6 behavior where
all scenarios ran as beauty - so any scenario that omits ``category`` keeps
its prior behavior. Adding a new declared category to the map is a one-line
change.

Scope (Fix 6 only)
------------------
This module changes nothing about the engine, no decision logic, no
detection logic, no renderer. It is harness-layer code that:

1. Loads scenario metadata.
2. Resolves the declared vertical for a given scenario.
3. Builds a per-scenario environment dict that sets ``VERTICAL_MODE``.
4. Optionally invokes ``python -m src.main`` as a subprocess with that env.
5. Optionally asserts ``receipts/engine_run.json::briefing_meta.vertical``
   matches the declared vertical.

It does NOT:

- Implement a reporter (Fix 7 territory).
- Run all six scenarios in a loop (callers do that explicitly).
- Re-baseline goldens.
- Change ``src/`` code.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional

import yaml

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent
SCENARIOS_YAML = REPO_ROOT / "tests" / "fixtures" / "synthetic_scenarios.yaml"
FIXTURES_DIR = REPO_ROOT / "tests" / "fixtures" / "synthetic"

# ---------------------------------------------------------------------------
# Vertical mapping
# ---------------------------------------------------------------------------
# Map the synthetic scenarios YAML ``category`` field to the engine's
# ``VERTICAL_MODE``. The engine itself only knows three vertical modes
# (see ``src.utils.VERTICAL_CONFIG``):
#
#   beauty | supplements | mixed
#
# The YAML uses more granular categories (beauty, supplement, lifestyle).
# This mapping is the contract.
#
# - "beauty"     -> "beauty"
# - "supplement" -> "supplements"   (note: engine VERTICAL_MODE uses the plural)
# - "lifestyle"  -> "mixed"         (no dedicated lifestyle vertical in engine)
#
# If a scenario omits ``category`` the harness falls back to
# :data:`DEFAULT_VERTICAL`.
CATEGORY_TO_VERTICAL: Dict[str, str] = {
    "beauty": "beauty",
    "supplement": "supplements",
    "supplements": "supplements",
    "lifestyle": "mixed",
    "mixed": "mixed",
}

# Default vertical when a scenario omits ``category``. We default to "beauty"
# explicitly because (a) it matches the historical pre-Fix-6 behavior so a
# missing field never silently degrades a scenario's run, and (b) it is the
# most-tested vertical in the engine. The default is intentional and
# documented; tests in test_matrix_vertical_propagation.py pin both the
# declared-category cases and the default-fallback case.
DEFAULT_VERTICAL: str = "beauty"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ScenarioRunResult:
    """Result of a synthetic scenario run."""
    scenario_name: str
    out_dir: Path
    declared_vertical: str
    actual_vertical: Optional[str]
    returncode: int
    stdout: str
    stderr: str

    @property
    def vertical_ok(self) -> bool:
        return self.actual_vertical == self.declared_vertical

    @property
    def briefing_html_path(self) -> Path:
        # main.py writes briefings under ``<out_dir>/briefings/<brand>_briefing.html``;
        # the exact filename depends on the ``--brand`` arg passed at run time.
        # Callers that need the briefing HTML should glob the briefings dir.
        return self.out_dir / "briefings"

    @property
    def engine_run_json_path(self) -> Path:
        return self.out_dir / "receipts" / "engine_run.json"


def load_scenarios(path: Optional[Path] = None) -> Dict[str, Dict[str, Any]]:
    """Load scenario metadata from synthetic_scenarios.yaml."""
    p = Path(path) if path is not None else SCENARIOS_YAML
    with open(p) as f:
        data = yaml.safe_load(f)
    return data["scenarios"]


def vertical_for_scenario(scenario_cfg: Mapping[str, Any]) -> str:
    """Resolve the engine ``VERTICAL_MODE`` for a scenario.

    Reads ``scenario_cfg["category"]`` and maps it via
    :data:`CATEGORY_TO_VERTICAL`. Falls back to :data:`DEFAULT_VERTICAL`
    when the field is missing or not in the map.
    """
    category = scenario_cfg.get("category")
    if category is None:
        return DEFAULT_VERTICAL
    key = str(category).strip().lower()
    return CATEGORY_TO_VERTICAL.get(key, DEFAULT_VERTICAL)


def build_env_for_scenario(
    scenario_cfg: Mapping[str, Any],
    *,
    base_env: Optional[Mapping[str, str]] = None,
    extra_v2_flags: bool = True,
) -> Dict[str, str]:
    """Build the subprocess environment for a single scenario.

    Always sets ``VERTICAL_MODE`` to the scenario's declared vertical.
    When ``extra_v2_flags`` is True (the default for synthetic-matrix
    use), also enables the V2 flag stack so the matrix exercises the
    V2 path (the synthetic e2e review explicitly runs the V2 stack).

    The base env defaults to ``os.environ`` minus any pre-existing
    ``VERTICAL_MODE`` / ``VERTICAL`` to avoid contamination from the
    operator shell.

    Always sets ``PYTHONPATH`` to the repo root so the subprocess can
    run from a ``.env``-free working directory (see :func:`run_scenario`
    for why we set ``cwd`` away from the repo).
    """
    env: Dict[str, str] = dict(base_env if base_env is not None else os.environ)
    # Strip any leftover vertical-mode hints from the surrounding shell;
    # the harness is the single source of truth for this run.
    env.pop("VERTICAL_MODE", None)
    env.pop("VERTICAL", None)

    vertical = vertical_for_scenario(scenario_cfg)
    env["VERTICAL_MODE"] = vertical

    # Make ``python -m src.main`` resolvable from any working directory
    # so the harness can run the subprocess outside the repo root and
    # therefore avoid the repo's ``.env`` clobbering the per-scenario
    # ``VERTICAL_MODE`` (the manual ``.env`` loader in ``src/utils.py``
    # unconditionally overwrites existing env vars when ``python-dotenv``
    # is not installed).
    existing_pp = env.get("PYTHONPATH", "").strip()
    if existing_pp:
        env["PYTHONPATH"] = f"{REPO_ROOT}{os.pathsep}{existing_pp}"
    else:
        env["PYTHONPATH"] = str(REPO_ROOT)

    if extra_v2_flags:
        # V2 stack flags. These match the synthetic-blocker e2e review's
        # invocation so the scenario runs through the V2 decision +
        # renderer path. Caller may override by passing extra_v2_flags=False
        # plus an explicit base_env.
        env.setdefault("ENGINE_V2_DECIDE", "true")
        env.setdefault("ENGINE_V2_OUTPUT", "true")
        env.setdefault("ENGINE_V2_SHADOW", "true")
        env.setdefault("ENGINE_V2_SIZING", "true")
        env.setdefault("STATS_NAN_FOR_HARDCODED", "true")
        env.setdefault("EVIDENCE_CLASS_ENFORCED", "true")
    return env


def orders_csv_for_scenario(scenario_name: str) -> Path:
    return FIXTURES_DIR / f"{scenario_name}_orders.csv"


def inventory_csv_for_scenario(scenario_name: str) -> Optional[Path]:
    p = FIXTURES_DIR / f"{scenario_name}_inventory.csv"
    return p if p.exists() else None


def run_scenario(
    scenario_name: str,
    out_dir: Path,
    *,
    scenarios: Optional[Dict[str, Dict[str, Any]]] = None,
    env_overrides: Optional[Mapping[str, str]] = None,
    extra_v2_flags: bool = True,
    timeout_sec: int = 300,
) -> ScenarioRunResult:
    """Run a single synthetic scenario via ``python -m src.main`` subprocess.

    Returns a :class:`ScenarioRunResult` with the declared vertical, the
    actually-stamped ``briefing_meta.vertical`` from
    ``receipts/engine_run.json`` (or ``None`` if the file was not produced
    or was unreadable), and the subprocess return code / stdout / stderr.

    Callers that want to fail loudly on a vertical mismatch should use
    :func:`assert_vertical_propagated` after this call.
    """
    if scenarios is None:
        scenarios = load_scenarios()
    if scenario_name not in scenarios:
        raise KeyError(
            f"Scenario {scenario_name!r} not found in {SCENARIOS_YAML}; "
            f"known: {sorted(scenarios.keys())}"
        )
    scenario_cfg = scenarios[scenario_name]
    declared_vertical = vertical_for_scenario(scenario_cfg)

    env = build_env_for_scenario(
        scenario_cfg,
        base_env=os.environ,
        extra_v2_flags=extra_v2_flags,
    )
    if env_overrides:
        env.update(dict(env_overrides))

    out_dir = Path(out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    orders_csv = orders_csv_for_scenario(scenario_name).resolve()
    if not orders_csv.exists():
        raise FileNotFoundError(
            f"Synthetic orders CSV not found for {scenario_name}: {orders_csv}"
        )

    cmd: List[str] = [
        sys.executable,
        "-m",
        "src.main",
        "--orders",
        str(orders_csv),
        "--brand",
        scenario_name,
        "--out",
        str(out_dir),
    ]
    inv = inventory_csv_for_scenario(scenario_name)
    if inv is not None:
        cmd += ["--inventory", str(inv.resolve())]

    # Run from out_dir (a fresh, empty tmp dir) so the engine's manual
    # .env fallback in src/utils.py does not pick up the repo root's
    # .env file and silently override our per-scenario VERTICAL_MODE.
    # PYTHONPATH (set in build_env_for_scenario) keeps ``python -m src.main``
    # importable from any cwd.
    proc = subprocess.run(
        cmd,
        env=env,
        cwd=str(out_dir),
        capture_output=True,
        text=True,
        timeout=timeout_sec,
    )

    actual_vertical = read_briefing_meta_vertical(out_dir)

    return ScenarioRunResult(
        scenario_name=scenario_name,
        out_dir=out_dir,
        declared_vertical=declared_vertical,
        actual_vertical=actual_vertical,
        returncode=proc.returncode,
        stdout=proc.stdout,
        stderr=proc.stderr,
    )


def read_briefing_meta_vertical(out_dir: Path) -> Optional[str]:
    """Return ``briefing_meta.vertical`` from ``<out_dir>/receipts/engine_run.json``.

    Returns ``None`` if the file is missing, unreadable, or does not carry
    a ``briefing_meta.vertical`` field.
    """
    p = Path(out_dir) / "receipts" / "engine_run.json"
    if not p.exists():
        return None
    try:
        with open(p) as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return None
    meta = data.get("briefing_meta") or {}
    v = meta.get("vertical")
    return str(v) if v is not None else None


def assert_vertical_propagated(result: ScenarioRunResult) -> None:
    """Raise AssertionError if the run did not stamp the declared vertical.

    Use this after :func:`run_scenario` to fail-hard on misconfiguration:
    a scenario YAML declared ``supplements`` but the engine ran as
    ``beauty`` is exactly the Fix 6 defect.
    """
    if result.actual_vertical is None:
        raise AssertionError(
            f"[{result.scenario_name}] receipts/engine_run.json::briefing_meta.vertical "
            f"is missing or unreadable at {result.engine_run_json_path}. "
            f"Subprocess returncode={result.returncode}.\n"
            f"stderr (last 500 chars): {result.stderr[-500:]}"
        )
    if result.actual_vertical != result.declared_vertical:
        raise AssertionError(
            f"[{result.scenario_name}] vertical mismatch: declared="
            f"{result.declared_vertical!r} but engine_run.json stamped="
            f"{result.actual_vertical!r}."
        )
