"""S8-T3.5 founder-tripwire probe.

Runs the healthy_beauty_240d fixture twice — once with
``ENGINE_V2_EB_BLEND=false`` and once with ``ENGINE_V2_EB_BLEND=true``
— and prints, for each Tier-B Recommended card (winback_dormant_cohort,
discount_dependency_hygiene, cohort_journey_first_to_second):

  - provenance block contents (None at flag-OFF; populated at flag-ON)
  - revenue_range.p10 / p50 / p90 (must be numerically identical
    across both flag states per DS verdict §2 + §5 invariants 1-10:
    the EB blend math is unchanged by S8-T3)

If the revenue numerics drift, T3.5 must be aborted and escalated.
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
WIRED_TIER_B_PLAYS = (
    "winback_dormant_cohort",
    "discount_dependency_hygiene",
    "cohort_journey_first_to_second",
)

BASE_ENV = {
    "ENGINE_V2_OUTPUT": "true",
    "ENGINE_V2_DECIDE": "true",
    "ENGINE_V2_SLATE": "true",
    "ENGINE_V2_SIZING": "true",
    "VERTICAL_MODE": "beauty",
    "WINDOW_POLICY": "auto",
    "ENGINE_V2_OBSERVED_EFFECT_WINBACK": "true",
    "ENGINE_V2_OBSERVED_EFFECT_DISCOUNT_HYGIENE": "true",
    "ENGINE_V2_OBSERVED_EFFECT_JOURNEY": "true",
    "ENGINE_V2_OBSERVED_ELIGIBILITY_GATE": "true",
    "ENGINE_V2_TIER_CHIP": "true",
    "ENGINE_V2_SENSITIVITY": "true",
}


def _run_with_flag(eb_blend: str) -> dict:
    env = dict(BASE_ENV)
    env["ENGINE_V2_EB_BLEND"] = eb_blend
    with tempfile.TemporaryDirectory() as td:
        out_dir = Path(td) / "probe"
        result = run_scenario(
            SCENARIO,
            out_dir,
            env_overrides=env,
            timeout_sec=300,
        )
        if result.returncode != 0:
            print(f"ERROR: scenario failed (EB_BLEND={eb_blend})")
            print(result.stderr[-1200:])
            sys.exit(1)
        run_path = out_dir / "receipts" / "engine_run.json"
        return json.loads(run_path.read_text())


def _find_card(run: dict, play_id: str) -> dict | None:
    for rec in (run.get("recommendations") or []):
        if (rec.get("play_id") or "") == play_id:
            return rec
    return None


def _summarize(run: dict) -> dict:
    out = {}
    for pid in WIRED_TIER_B_PLAYS:
        card = _find_card(run, pid)
        if card is None:
            out[pid] = None
            continue
        rr = card.get("revenue_range") or {}
        out[pid] = {
            "p10": rr.get("p10"),
            "p50": rr.get("p50"),
            "p90": rr.get("p90"),
            "source": rr.get("source"),
            "suppressed": rr.get("suppressed"),
            "provenance": card.get("provenance"),
            "evidence_source": card.get("evidence_source"),
            "sensitivity_present": card.get("sensitivity") is not None,
        }
    return out


def main() -> int:
    print("=== S8-T3.5 tripwire: pre-flip (EB_BLEND=false) ===")
    pre = _summarize(_run_with_flag("false"))
    for pid, payload in pre.items():
        print(f"\n[{pid}]")
        print(json.dumps(payload, indent=2, default=str))

    print("\n\n=== S8-T3.5 tripwire: post-flip (EB_BLEND=true) ===")
    post = _summarize(_run_with_flag("true"))
    for pid, payload in post.items():
        print(f"\n[{pid}]")
        print(json.dumps(payload, indent=2, default=str))

    print("\n\n=== INVARIANT CHECK: revenue_range numerics unchanged ===")
    drift = False
    for pid in WIRED_TIER_B_PLAYS:
        a = pre.get(pid)
        b = post.get(pid)
        if a is None and b is None:
            print(f"  {pid}: NOT PRESENT in either run (skip)")
            continue
        if a is None or b is None:
            print(f"  {pid}: PRESENCE DRIFT (pre={a is not None}, post={b is not None}) - FAIL")
            drift = True
            continue
        same = (a["p10"] == b["p10"] and a["p50"] == b["p50"] and a["p90"] == b["p90"])
        status = "OK" if same else "DRIFT - FAIL"
        print(f"  {pid}: pre=({a['p10']},{a['p50']},{a['p90']}) "
              f"post=({b['p10']},{b['p50']},{b['p90']}) -> {status}")
        if not same:
            drift = True

    print("\n=== INVARIANT CHECK: provenance populates only at flag-ON ===")
    for pid in WIRED_TIER_B_PLAYS:
        a = pre.get(pid)
        b = post.get(pid)
        if a is None or b is None:
            continue
        pre_p = a.get("provenance")
        post_p = b.get("provenance")
        ok = (pre_p is None) and (post_p is not None)
        print(f"  {pid}: pre_provenance={pre_p is not None} post_provenance={post_p is not None} "
              f"-> {'OK' if ok else 'CHECK'}")

    return 1 if drift else 0


if __name__ == "__main__":
    sys.exit(main())
