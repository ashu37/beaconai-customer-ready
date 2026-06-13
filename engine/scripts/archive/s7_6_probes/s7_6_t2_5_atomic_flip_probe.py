"""S7.6-T2.5-atomic-flip probe.

Runs both Beauty + Supplements pinned synthetic-slate fixtures with
ENGINE_V2_BUILDER_REPLENISHMENT_DUE=true (plus observed-effect, decide,
output, slate, priors-validation) and dumps:
  - audience_size for replenishment_due
  - slate position (Recommended / Considered / Experiment / Watching)
  - reason if Considered
  - full slate composition

Decision rule (per spec):
  - Beauty audience_size >= 10 -> PROCEED to flip
  - Beauty audience_size < 10  -> STOP
  - Beauty audience exists but play disappears downstream -> STOP and trace
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


ENV_OVERRIDES_COMMON = {
    "ENGINE_V2_OUTPUT": "true",
    "ENGINE_V2_DECIDE": "true",
    "ENGINE_V2_SLATE": "true",
    "ENGINE_V2_SIZING": "true",
    "ENGINE_V2_PRIORS_VALIDATION": "true",
    "WINDOW_POLICY": "auto",
    "ENGINE_V2_OBSERVED_EFFECT_REPLENISHMENT": "true",
    "ENGINE_V2_BUILDER_REPLENISHMENT_DUE": "true",
}

REPL_PLAY_IDS = {"replenishment_due", "replenishment_due_cohort"}


def _section_play_ids(items):
    return [(i.get("play_id"), i.get("reason_code") or i.get("reason"))
            for i in (items or [])]


def _find_in(items, play_ids):
    for i in (items or []):
        if (i.get("play_id") or "") in play_ids:
            return i
    return None


def probe(scenario: str, vertical: str) -> dict:
    env = dict(ENV_OVERRIDES_COMMON)
    env["VERTICAL_MODE"] = vertical
    with tempfile.TemporaryDirectory() as td:
        out_dir = Path(td) / "probe"
        result = run_scenario(scenario, out_dir, env_overrides=env, timeout_sec=300)
        if result.returncode != 0:
            print(f"ERROR: scenario {scenario} failed")
            print(result.stderr[-1500:])
            return {"error": True}

        run = json.loads((out_dir / "receipts" / "engine_run.json").read_text())

        recs = run.get("recommendations") or []
        considered = run.get("considered") or []
        experiments = run.get("experiments") or run.get("recommended_experiments") or []
        watching = run.get("watching") or []

        print(f"\n=== {scenario} ({vertical}) ===")
        print(f"Recommended ({len(recs)}): {_section_play_ids(recs)}")
        print(f"Considered ({len(considered)}): {_section_play_ids(considered)}")
        print(f"Experiments ({len(experiments)}): {_section_play_ids(experiments)}")
        print(f"Watching ({len(watching)}): {_section_play_ids(watching)}")

        # Find replenishment_due wherever it lives
        location = None
        card = _find_in(recs, REPL_PLAY_IDS)
        if card:
            location = "Recommended"
        if card is None:
            card = _find_in(considered, REPL_PLAY_IDS)
            if card:
                location = "Considered"
        if card is None:
            card = _find_in(experiments, REPL_PLAY_IDS)
            if card:
                location = "Experiment"
        if card is None:
            card = _find_in(watching, REPL_PLAY_IDS)
            if card:
                location = "Watching"

        if card is None:
            print(f"replenishment_due: NOT FOUND in any slate section")
            # Look for builder-emitted audience_size in candidates
            cands = run.get("candidates") or []
            print(f"Candidates ({len(cands)}): {_section_play_ids(cands)}")
            return {"vertical": vertical, "location": None, "audience_size": 0}

        # Pull audience_size + reason
        aud_size = card.get("audience_size") or card.get("audience", {}).get("size")
        reason = card.get("reason_code") or card.get("reason")
        print(f"replenishment_due location: {location}")
        print(f"  audience_size: {aud_size}")
        print(f"  reason: {reason}")
        # Try to get blend_provenance
        rr = card.get("revenue_range") or {}
        drivers = rr.get("drivers") or []
        bp = next((d for d in drivers if isinstance(d, dict) and d.get("name") == "blend_provenance"), None)
        if bp:
            print(f"  observed_n: {bp.get('observed_n')}, observed_k: {bp.get('observed_k')}")
            print(f"  posterior_value: {bp.get('posterior_value')} (ratio: {bp.get('posterior_ratio')})")
            print(f"  sign_agreement: {bp.get('observed_sign_agreement_count')}, dominant: {bp.get('observed_dominant_sign')}")
        return {"vertical": vertical, "location": location, "audience_size": aud_size, "reason": reason}


def main() -> int:
    print(">>> Probing Beauty + Supplements pinned synthetic-slate fixtures")
    print(">>> ENGINE_V2_BUILDER_REPLENISHMENT_DUE=true (atomic-flip precondition)")
    b = probe("healthy_beauty_240d", "beauty")
    s = probe("healthy_supplements_240d", "supplements")

    print("\n=== DECISION ===")
    b_size = b.get("audience_size") or 0
    try:
        b_size_int = int(b_size)
    except (TypeError, ValueError):
        b_size_int = 0
    if b.get("location") is None:
        print("STOP: replenishment_due silently dropped on Beauty. Trace required.")
        return 2
    if b_size_int >= 10:
        print(f"PROCEED: Beauty audience_size={b_size_int} >= 10; Beauty location={b['location']}")
        return 0
    print(f"STOP: Beauty audience_size={b_size_int} < 10. Floor still binding.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
