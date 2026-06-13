"""S8-T1.5 founder-tripwire probe (dry-run, no commits).

Runs the healthy_beauty_240d fixture with ENGINE_V2_TIER_CHIP=true and
prints the evidence_source + observed_n on every Tier-B Recommended card
so the founder can verify the chip populates as predicted before flip.

Also runs healthy_supplements_240d to confirm no Tier-B card carries the
chip (per S7.6 close: aov_bundle vertically excluded, replenishment_due
dormant).
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tests.synthetic_harness import run_scenario  # noqa: E402


TIER_B = {
    "winback_dormant_cohort",
    "discount_dependency_hygiene",
    "cohort_journey_first_to_second",
    "aov_lift_via_threshold_bundle",
    "replenishment_due",
}


def _flatten_measurement_n(card: dict) -> object:
    m = card.get("measurement") or {}
    return m.get("n") or m.get("observed_n")


def _print_scenario(scenario: str, vertical: str) -> None:
    env = {
        "ENGINE_V2_OUTPUT": "true",
        "ENGINE_V2_DECIDE": "true",
        "ENGINE_V2_SLATE": "true",
        "ENGINE_V2_SIZING": "true",
        "VERTICAL_MODE": vertical,
        "WINDOW_POLICY": "auto",
        "ENGINE_V2_TIER_CHIP": "true",
    }
    with tempfile.TemporaryDirectory() as td:
        out_dir = Path(td) / "probe"
        result = run_scenario(scenario, out_dir, env_overrides=env, timeout_sec=300)
        if result.returncode != 0:
            print(f"ERROR scenario={scenario}")
            print(result.stderr[-800:])
            return
        run_path = out_dir / "receipts" / "engine_run.json"
        run = json.loads(run_path.read_text())
        print(f"\n=== {scenario} (vertical={vertical}) ===")
        for section_name in ("recommendations", "considered"):
            cards = run.get(section_name) or []
            for c in cards:
                pid = c.get("play_id") or ""
                if pid not in TIER_B:
                    continue
                ev = c.get("evidence_source")
                n = _flatten_measurement_n(c)
                print(f"  [{section_name}] play_id={pid} evidence_source={ev!r} measurement.n={n}")


def main() -> int:
    _print_scenario("healthy_beauty_240d", "beauty")
    _print_scenario("healthy_supplements_240d", "supplements")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
