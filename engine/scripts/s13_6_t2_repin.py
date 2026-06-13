"""S13.6-T2 engine_run.json re-pin helper.

Founder + DS approved 2026-05-30/31 (sibling of T1a/T1b per DS R5 atomic
split). Computes post-strip engine_run.json SHA on the 5 pinned
synthetic_scenarios.yaml fixtures after:

- Typing the three EngineRun ``Any`` slots (StoreProfile / ModelCard /
  RetentionCard) — typing alone SHOULD NOT change the serialized SHA
  (annotation-level only; ``_to_jsonable`` recursion shape unchanged).
- Removing ``PlayCard.klaviyo_brief_inputs`` entirely — this WILL drop
  the empty-dict key from every emitted PlayCard, so the SHA WILL move.

Modeled on ``scripts/s13_6_t1b_repin.py``.

Caveat (carried forward from S13-T3.5 and T1a/T1b): engine_run.json
contains wall-clock ``fit_timestamp`` values from S10-S12 ML ModelCards,
so the SHAs printed here record the at-commit moment only. The
load-bearing post-T2 test gates are the structural strip + AST sweep +
dataclass introspection tests in
``tests/test_s13_6_t2_typed_any_slots.py`` and the extended renderer
non-consumption grep pin in
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
    print("S13.6-T2 engine_run.json SHA re-pin")
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
