"""S13.6-T7a engine_run.json re-pin helper.

Per DS adjudication 2026-06-01 + founder approved 2026-06-01: captures
the post-T7a ``engine_run.json`` SHA on the 5 pinned
``tests/fixtures/synthetic_scenarios.yaml`` fixtures after:

- Adding 3 closed-set null-reason enums in ``src/engine_run.py``:
  ``RevenueRangeSuppressionReason`` (9 members),
  ``MonthDeltaNullReason`` (5 members), and
  ``PredictedSegmentNullReason`` (4 members).
- Adding 3 paired ``_null_reason`` fields:
  ``RevenueRange.suppression_reason``,
  ``EngineRun.month_2_delta_null_reason``, and
  ``PredictedSegment.segment_name_null_reason``.
- Wrapping the 7 ``RevenueRange`` suppression-string producer sites
  in ``src/sizing.py``, ``src/measurement_builder.py`` (3), and
  ``src/decide.py`` (1) at the seam per DS Q1 (NO producer rewrites).
- Refactoring ``src.predictive.month_2_delta.detect_month_2_delta`` to
  return a 2-tuple ``(Optional[MonthDelta], Optional[MonthDeltaNullReason])``
  (Option (a) per the brief — tuple-return enforces always-paired
  emission at the seam).
- Refactoring ``src.predictive.consumer_wiring._compute_modal_segment``
  to return a 4-tuple with the paired ``PredictedSegmentNullReason``.

JSON shape changes (post-T7a):

    RevenueRange:       + "suppression_reason": "<member_value>" | null
    EngineRun:          + "month_2_delta_null_reason": "<member_value>" | null
    PredictedSegment:   + "segment_name_null_reason": "<member_value>" | null

The SHA on every emitted RevenueRange + every EngineRun + every
PredictedSegment WILL move. Re-pin via this script + the ledger entry
at ``tests/fixtures/pinned_sha_ledger.json``.

Modeled on ``scripts/s13_6_t6_repin.py``.

Caveat (carried forward from S13-T3.5 and T1a/T1b/T2/T3/T4/T5/T6):
``engine_run.json`` contains wall-clock ``fit_timestamp`` values from
the S10-S12 ML ModelCards, so the SHAs printed here record the
at-commit moment only. The load-bearing post-T7a test gates are the
AST sweep + paired-invariant tests in
``tests/test_s13_6_t7a_no_silent_nulls.py`` — NOT this ledger.
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
    print("S13.6-T7a engine_run.json SHA re-pin")
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
