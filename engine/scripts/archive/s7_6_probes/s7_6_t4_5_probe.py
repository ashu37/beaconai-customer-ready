"""S7.6-T4.5 founder-tripwire probe (dry-run, no commits).

Runs the healthy_beauty_240d AND healthy_supplements_240d fixtures with
``ENGINE_V2_OBSERVED_EFFECT_JOURNEY=true`` and prints the
cohort_journey_first_to_second card's blend_provenance so the IM/founder
can decide whether to flip the flag.

B-4 is wildcard-vertical (priors.yaml:1016-1035 per agent note); supplements
may also produce observed-effect if its first-to-second cohort is non-empty.

Berkson rule: cohort denominator MUST use early-half-of-window first-purchase
dates per tests/test_berkson_invariant.py + project_journey_p_zero.md.
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


ENV_OVERRIDES_BASE = {
    "ENGINE_V2_OUTPUT": "true",
    "ENGINE_V2_DECIDE": "true",
    "ENGINE_V2_SLATE": "true",
    "ENGINE_V2_SIZING": "true",
    "ENGINE_V2_PRIORS_VALIDATION": "true",
    "ENGINE_V2_STORE_PROFILE": "true",
    "ENGINE_V2_BUILDER_JOURNEY_FIRST_TO_SECOND": "true",
    "ENGINE_V2_OBSERVED_EFFECT_JOURNEY": "true",
    "WINDOW_POLICY": "auto",
}

PLAY_ID = "cohort_journey_first_to_second"


def _find_card(run: dict):
    for rec in run.get("recommendations") or []:
        if (rec.get("play_id") or "") == PLAY_ID:
            return rec, "Recommended"
    for sec in run.get("considered") or []:
        if (sec.get("play_id") or "") == PLAY_ID:
            return sec, "Considered"
    for sec in run.get("watching") or []:
        if (sec.get("play_id") or "") == PLAY_ID:
            return sec, "Watching"
    return None, None


def _dump(scenario: str, vertical: str) -> None:
    env = dict(ENV_OVERRIDES_BASE)
    env["VERTICAL_MODE"] = vertical
    with tempfile.TemporaryDirectory() as td:
        out_dir = Path(td) / "probe"
        result = run_scenario(scenario, out_dir, env_overrides=env, timeout_sec=300)
        if result.returncode != 0:
            print(f"ERROR: scenario {scenario} failed")
            print(result.stderr[-800:])
            return

        run = json.loads((out_dir / "receipts" / "engine_run.json").read_text())
        card, role = _find_card(run)
        print(f"\n=== {scenario} ({vertical}) ===")
        if card is None:
            print(f"No {PLAY_ID} card in run (any role).")
            return
        print(f"role : {role}")
        rr = card.get("revenue_range") or {}
        drivers = rr.get("drivers") or []
        bp = next(
            (d for d in drivers if isinstance(d, dict) and d.get("name") == "blend_provenance"),
            None,
        )
        if bp is None:
            print("No blend_provenance driver found.")
            return
        print(f"prior_value            : {bp.get('prior_value')}")
        print(f"pseudo_n               : {bp.get('pseudo_n')}")
        print(f"observed_k             : {bp.get('observed_k')}")
        print(f"observed_n             : {bp.get('observed_n')}")
        print(f"store_data_status      : {bp.get('store_data_status')}")
        print(f"posterior_value        : {bp.get('posterior_value')}")
        print(f"posterior_ratio        : {bp.get('posterior_ratio')}")
        print(f"observed_sign_agreement: {bp.get('observed_sign_agreement_count')}")
        print(f"observed_dominant_sign : {bp.get('observed_dominant_sign')}")
        windows = bp.get("observed_windows") or {}
        for w, payload in windows.items():
            print(f"  window {w}: {payload}")


def main() -> int:
    _dump("healthy_beauty_240d", "beauty")
    _dump("healthy_supplements_240d", "supplements")
    return 0


if __name__ == "__main__":
    sys.exit(main())
