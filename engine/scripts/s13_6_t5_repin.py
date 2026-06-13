"""S13.6-T5 engine_run.json re-pin helper.

Per founder lock-in #3 (2026-05-30): hard freeze at v2.0.0 after
S13.6. This script captures the post-T5 ``engine_run.json`` SHA on
the 5 pinned ``tests/fixtures/synthetic_scenarios.yaml`` fixtures
after bumping ``EngineRun.schema_version`` literal default
``"1.0.0"`` -> ``"2.0.0"`` and adding the CHANGELOG block at the
top of ``src/engine_run.py``.

JSON shape change (post-T5):

    Before: "schema_version": "1.0.0", ...
    After:  "schema_version": "2.0.0", ...

The SHA on every fixture's ``engine_run.json`` WILL move (single
top-level string field change, present on every emission).

Modeled on ``scripts/s13_6_t4_repin.py``.

Caveat (carried forward from S13-T3.5 and T1a/T1b/T2/T3/T4):
``engine_run.json`` contains wall-clock ``fit_timestamp`` values
from the S10-S12 ML ModelCards, so the SHAs printed here record the
at-commit moment only. The load-bearing post-T5 test gates are the
dataclass-default introspection + emitted-JSON value assertion +
CHANGELOG anchor-phrase pin in
``tests/test_s13_6_t5_schema_version_2_0_0.py`` — NOT this ledger.
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
    print("S13.6-T5 engine_run.json SHA re-pin")
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
