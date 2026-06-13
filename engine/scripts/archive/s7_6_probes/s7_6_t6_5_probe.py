"""S7.6-T6.5 founder-tripwire probe (dry-run, no commits).

Enumerates per-card eligibility-gate verdict + 3-state copy ladder state
across all five Tier-B plays on healthy_beauty_240d + healthy_supplements_240d
fixtures with ``ENGINE_V2_OBSERVED_ELIGIBILITY_GATE=true`` (and observed-effect
builders T1/T3/T4 ON; T5 aov_bundle deliberately OFF — T5.5 is the next
dispatch, not this one).

Decision rule per IM spec:
- All currently-active observed-effect plays still surface where they previously
  surfaced (no SIGNAL_INCONSISTENT_ACROSS_WINDOWS downgrades): PROCEED.
- Any currently-active play unexpectedly demotes to Considered with
  SIGNAL_INCONSISTENT_ACROSS_WINDOWS: STOP.
- aov_bundle unexpectedly downgrades (T5 flag OFF → gate should be no-op): STOP.
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
    "ENGINE_V2_OBSERVED_ELIGIBILITY_GATE": "true",
    "ENGINE_V2_OBSERVED_EFFECT_WINBACK": "true",
    "ENGINE_V2_OBSERVED_EFFECT_DISCOUNT_HYGIENE": "true",
    "ENGINE_V2_OBSERVED_EFFECT_JOURNEY": "true",
    # AOV bundle observed-effect deliberately NOT enabled here; T5.5 next.
    "ENGINE_V2_DECIDE": "true",
    "ENGINE_V2_OUTPUT": "true",
    "ENGINE_V2_SLATE": "true",
    "ENGINE_V2_PRIORS_VALIDATION": "true",
    "ENGINE_V2_STORE_PROFILE": "true",
    "WINDOW_POLICY": "auto",
}

PLAYS = [
    "winback_dormant_cohort",
    "discount_dependency_hygiene",
    "cohort_journey_first_to_second",
    "aov_lift_via_threshold_bundle",
    "replenishment_due",
]


def _find_card(run: dict, play_id: str):
    for rec in run.get("recommendations") or []:
        if (rec.get("play_id") or "") == play_id:
            return rec, "Recommended"
    for sec in run.get("considered") or []:
        if (sec.get("play_id") or "") == play_id:
            return sec, "Considered"
    for sec in run.get("watching") or []:
        if (sec.get("play_id") or "") == play_id:
            return sec, "Watching"
    return None, "Nowhere"


def _bp(card):
    if card is None:
        return None
    rr = card.get("revenue_range") or {}
    drivers = rr.get("drivers") or []
    return next(
        (d for d in drivers if isinstance(d, dict) and d.get("name") == "blend_provenance"),
        None,
    )


def _dump(scenario: str, vertical: str) -> None:
    env = dict(ENV_OVERRIDES_BASE)
    env["VERTICAL_MODE"] = vertical
    with tempfile.TemporaryDirectory() as td:
        out_dir = Path(td) / "probe"
        result = run_scenario(scenario, out_dir, env_overrides=env, timeout_sec=300)
        if result.returncode != 0:
            print(f"ERROR: scenario {scenario} failed")
            print(result.stderr[-1200:])
            return

        run = json.loads((out_dir / "receipts" / "engine_run.json").read_text())
        print(f"\n=== {scenario} ({vertical}) ===")
        for pid in PLAYS:
            card, role = _find_card(run, pid)
            print(f"\n[{pid}] role={role}")
            if card is None:
                print("  (no card)")
                continue
            wy = card.get("why_now") or card.get("why") or ""
            print(f"  why_now: {wy[:160]!r}")
            reason = card.get("considered_reason") or card.get("reason_code")
            if reason:
                print(f"  considered_reason: {reason}")
            bp = _bp(card)
            if bp is None:
                print("  (no blend_provenance driver)")
                continue
            print(f"  observed_n  : {bp.get('observed_n')}")
            print(f"  observed_k  : {bp.get('observed_k')}")
            print(f"  prior_value : {bp.get('prior_value')}")
            print(f"  posterior   : {bp.get('posterior_value')}")
            print(f"  post_ratio  : {bp.get('posterior_ratio')}")
            print(f"  sign_agree  : {bp.get('observed_sign_agreement_count')}")
            print(f"  dom_sign    : {bp.get('observed_dominant_sign')}")
            wins = bp.get("observed_windows") or {}
            for w, payload in wins.items():
                print(f"    win {w}: {payload}")


def main() -> int:
    _dump("healthy_beauty_240d", "beauty")
    _dump("healthy_supplements_240d", "supplements")
    return 0


if __name__ == "__main__":
    sys.exit(main())
