"""S13.6-T3 engine_run.json re-pin helper.

Founder + DS approved 2026-05-30 (sibling of T1a/T1b/T2 per DS R5 atomic
split). Computes post-restructure engine_run.json SHA on the 5 pinned
synthetic_scenarios.yaml fixtures after:

- Introducing ``NonLiftAtom`` (the typed wrapper for the four addressable-
  opportunity numerics per DS R1, founder approved 2026-05-30).
- Restructuring ``OpportunityContext`` so its four monetary numerics now
  live inside ``non_lift: NonLiftAtom`` — this WILL change the JSON shape
  of every PlayCard's ``opportunity_context`` block, so the SHA WILL move.
- Stripping the DS-locked duplicates ``aov`` and ``addressable_value``
  from ``OpportunityContext`` (replaced by ``non_lift.aov_used`` and
  ``non_lift.value`` / ``non_lift.monthly_revenue_estimate``).

Modeled on ``scripts/s13_6_t2_repin.py``.

Caveat (carried forward from S13-T3.5 and T1a/T1b/T2): engine_run.json
contains wall-clock ``fit_timestamp`` values from S10-S12 ML ModelCards,
so the SHAs printed here record the at-commit moment only. The
load-bearing post-T3 test gates are the structural restructure +
NonLiftAtom dataclass introspection + AST sweep + extended renderer
non-consumption grep pin in
``tests/test_s13_6_t3_non_lift_atom_wrapper.py`` and
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
    print("S13.6-T3 engine_run.json SHA re-pin")
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
