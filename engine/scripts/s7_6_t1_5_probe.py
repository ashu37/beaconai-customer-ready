"""S7.6-T1.5 founder-tripwire probe (dry-run, no commits).

Runs the healthy_beauty_240d fixture with
``ENGINE_V2_OBSERVED_EFFECT_WINBACK=true`` and prints the
winback_dormant_cohort card's observed_k / observed_n / posterior_value
/ posterior_ratio so the IM/founder can decide whether to flip the flag.
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


SCENARIO = "healthy_beauty_240d"
ENV_OVERRIDES = {
    "ENGINE_V2_OUTPUT": "true",
    "ENGINE_V2_DECIDE": "true",
    "ENGINE_V2_SLATE": "true",
    "ENGINE_V2_SIZING": "true",
    "VERTICAL_MODE": "beauty",
    "WINDOW_POLICY": "auto",
    "ENGINE_V2_OBSERVED_EFFECT_WINBACK": "true",
}


def _walk_recommendations(engine_run: dict):
    return list(engine_run.get("recommendations") or [])


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        out_dir = Path(td) / "probe"
        result = run_scenario(
            SCENARIO,
            out_dir,
            env_overrides=ENV_OVERRIDES,
            timeout_sec=300,
        )
        if result.returncode != 0:
            print("ERROR: scenario failed")
            print(result.stderr[-800:])
            return 1

        run_path = out_dir / "receipts" / "engine_run.json"
        run = json.loads(run_path.read_text())

        winback_card = None
        for rec in _walk_recommendations(run):
            if (rec.get("play_id") or "") == "winback_dormant_cohort":
                winback_card = rec
                break

        if winback_card is None:
            # Also check considered (in case it routed there)
            for sec in (run.get("considered") or []):
                if (sec.get("play_id") or "") == "winback_dormant_cohort":
                    winback_card = sec
                    print("NOTE: winback_dormant_cohort found in CONSIDERED, not Recommended")
                    break

        if winback_card is None:
            print("No winback_dormant_cohort card in this run.")
            return 0

        rr = winback_card.get("revenue_range") or {}
        drivers = rr.get("drivers") or []
        bp = next(
            (d for d in drivers if isinstance(d, dict) and d.get("name") == "blend_provenance"),
            None,
        )
        if bp is None:
            print("No blend_provenance driver found on winback card.")
            return 0

        print("=== S7.6-T1.5 Beauty observed-effect probe ===")
        print(f"play_id                : {winback_card.get('play_id')}")
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
        return 0


if __name__ == "__main__":
    sys.exit(main())
