"""S7.6-T7.5 founder-tripwire probe (dry-run, no commits).

Runs healthy_beauty_240d and healthy_supplements_240d with
``ENGINE_V2_AOV_THRESHOLD_FROM_DATA=true`` and prints, for each:
  - Beauty: L90 order count, computed threshold, threshold_source,
    audience size.
  - Supplements: should refuse with vertical_excluded_per_b5_248.

No observed_n threshold here (T7 is a bug fix, not observed-effect
wiring). Success = non-empty Beauty audience + supplements refused.
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


COMMON_ENV = {
    "ENGINE_V2_OUTPUT": "true",
    "ENGINE_V2_DECIDE": "true",
    "ENGINE_V2_SLATE": "true",
    "ENGINE_V2_SIZING": "true",
    "ENGINE_V2_BUILDER_AOV_BUNDLE": "true",
    "ENGINE_V2_AOV_THRESHOLD_FROM_DATA": "true",
    "WINDOW_POLICY": "auto",
}

PLAY_ID = "aov_lift_via_threshold_bundle"


def _walk(engine_run: dict):
    out = []
    out.extend(engine_run.get("recommendations") or [])
    out.extend(engine_run.get("considered") or [])
    out.extend(engine_run.get("watching") or [])
    out.extend(engine_run.get("recommended_experiments") or [])
    return out


def _find_card(run: dict):
    for c in _walk(run):
        if (c.get("play_id") or "") == PLAY_ID:
            return c
    return None


def _probe(scenario: str, vertical: str):
    print(f"\n=== {scenario} (vertical={vertical}) ===")
    env = dict(COMMON_ENV)
    env["VERTICAL_MODE"] = vertical
    with tempfile.TemporaryDirectory() as td:
        out_dir = Path(td) / "probe"
        result = run_scenario(scenario, out_dir, env_overrides=env, timeout_sec=300)
        if result.returncode != 0:
            print("ERROR: scenario failed")
            print(result.stderr[-800:])
            return None

        run_path = out_dir / "receipts" / "engine_run.json"
        run = json.loads(run_path.read_text())

        card = _find_card(run)
        rec_ids = [r.get("play_id") for r in (run.get("recommendations") or [])]
        cons_ids = [c.get("play_id") for c in (run.get("considered") or [])]
        watch_ids = [w.get("play_id") for w in (run.get("watching") or [])]
        exp_ids = [e.get("play_id") for e in (run.get("recommended_experiments") or [])]
        print(f"recommendations: {rec_ids}")
        print(f"considered     : {cons_ids}")
        print(f"watching       : {watch_ids}")
        print(f"experiments    : {exp_ids}")
        # also dump rejected_plays for aov_bundle
        rej = run.get("rejected_plays") or []
        for r in rej:
            if (r.get("play_id") or "") == PLAY_ID:
                print(f"REJECTED entry: {r}")
                break
        # dump top-level keys
        print(f"top-level keys: {list(run.keys())}")
        # search every value for aov_lift mention
        import json as _j
        flat = _j.dumps(run)
        if PLAY_ID in flat:
            print(f"  PLAY_ID appears in engine_run.json ({flat.count(PLAY_ID)} times)")
            # walk and find paths
            def _walk_path(obj, path=""):
                hits = []
                if isinstance(obj, dict):
                    for k, v in obj.items():
                        if isinstance(v, str) and PLAY_ID in v:
                            hits.append((path + "/" + k, v[:120]))
                        else:
                            hits.extend(_walk_path(v, path + "/" + k))
                elif isinstance(obj, list):
                    for i, v in enumerate(obj):
                        if isinstance(v, str) and PLAY_ID in v:
                            hits.append((path + f"[{i}]", v[:120]))
                        else:
                            hits.extend(_walk_path(v, path + f"[{i}]"))
                return hits
            paths = _walk_path(run)
            for p, v in paths:
                print(f"    path: {p} = {v!r}")
        else:
            print(f"  PLAY_ID does NOT appear anywhere in engine_run.json")

        if card is None:
            print(f"NOTE: {PLAY_ID} not present anywhere in slate.")
        else:
            print(f"FOUND {PLAY_ID} card:")
            print(f"  audience_size    : {card.get('audience_size')}")
            print(f"  rejection_reason : {card.get('preliminary_rejection_reason') or card.get('rejection_reason')}")
            print(f"  threshold_source : {card.get('threshold_source')}")
            # any explicit threshold fields
            for k in ("threshold", "aov_threshold", "threshold_usd"):
                if k in card:
                    print(f"  {k}: {card.get(k)}")
        # Also dump briefing path for sha256 capture downstream
        briefing = out_dir / "briefing.html"
        if briefing.exists():
            import hashlib
            sha = hashlib.sha256(briefing.read_bytes()).hexdigest()
            print(f"briefing.html sha256: {sha}")
        return run


def main() -> int:
    _probe("healthy_beauty_240d", "beauty")
    _probe("healthy_supplements_240d", "supplements")
    return 0


if __name__ == "__main__":
    sys.exit(main())
