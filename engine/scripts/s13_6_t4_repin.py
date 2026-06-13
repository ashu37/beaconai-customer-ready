"""S13.6-T4 engine_run.json re-pin helper.

Founder + DS approved 2026-05-31 (sibling of T1a/T1b/T2/T3 per DS R5
atomic split). Computes post-restructure engine_run.json SHA on the 5
pinned synthetic_scenarios.yaml fixtures after:

- Introducing typed ``FitWarning`` + ``FitWarningLevel`` on
  ``src/engine_run.py`` (per D-S13-4 structural).
- Changing ``ModelCardRef.fit_warnings: List[str]`` ->
  ``List[FitWarning]``.
- Rewiring the producer
  ``src/predictive/ranking_strategy.py::rank_audience`` to emit typed
  FitWarning instances instead of ``"{LEVEL}:{substrate}"`` strings.

JSON shape change (post-T4):

    Before: "fit_warnings": ["PROVISIONAL_SELECTED:cf", ...]
    After:  "fit_warnings": [{"level": "PROVISIONAL_SELECTED",
                              "substrate": "cf"}, ...]

The SHA on every recommendation card that carries a populated
``model_card_ref.fit_warnings`` WILL move; cards with empty fit_warnings
are unaffected.

Modeled on ``scripts/s13_6_t3_repin.py``.

Caveat (carried forward from S13-T3.5 and T1a/T1b/T2/T3): engine_run.json
contains wall-clock ``fit_timestamp`` values from S10-S12 ML ModelCards,
so the SHAs printed here record the at-commit moment only. The
load-bearing post-T4 test gates are the structural FitWarning dataclass
introspection + producer-emission unit test + AST sweep + extended
renderer non-consumption grep pin in
``tests/test_s13_6_t4_fit_warning_typed.py`` and
``tests/test_s13_renderer_non_consumption.py`` — NOT this ledger.
"""
from __future__ import annotations

import hashlib
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tests.synthetic_harness import run_scenario  # noqa: E402

ENV_BASE = {
    "ENGINE_V2_OUTPUT": "true",
    "ENGINE_V2_DECIDE": "true",
    "ENGINE_V2_SLATE": "true",
    "ENGINE_V2_SIZING": "true",
    "WINDOW_POLICY": "auto",
}

SCENARIOS = [
    ("healthy_beauty_240d", "beauty"),
    ("healthy_supplements_240d", "supplements"),
    ("small_store_240d", "beauty"),
    ("cold_start_45d", "beauty"),
    ("healthy_beauty_low_inventory_240d", "beauty"),
]


def main() -> int:
    print("S13.6-T4 engine_run.json SHA re-pin")
    print("=" * 60)
    for scenario, vertical in SCENARIOS:
        env = dict(ENV_BASE)
        env["VERTICAL_MODE"] = vertical
        with tempfile.TemporaryDirectory(prefix=f"{scenario}_") as td:
            res = run_scenario(
                scenario, Path(td) / "out",
                env_overrides=env, timeout_sec=300,
            )
            if res.returncode != 0:
                print(f"FAIL {scenario}: {res.stderr[-500:]}")
                continue
            er_path = res.engine_run_json_path
            if not er_path.exists():
                print(f"{scenario}: engine_run.json NOT PRODUCED")
                continue
            sha = hashlib.sha256(er_path.read_bytes()).hexdigest()
            print(f"  {scenario}: {sha}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
