"""Deep-inspect Beauty engine_run.json for aov_lift_via_threshold_bundle."""
import json, sys, tempfile
from pathlib import Path
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
from tests.synthetic_harness import run_scenario

env = {
    "ENGINE_V2_OUTPUT": "true",
    "ENGINE_V2_DECIDE": "true",
    "ENGINE_V2_SLATE": "true",
    "ENGINE_V2_SIZING": "true",
    "ENGINE_V2_PRIORS_VALIDATION": "true",
    "ENGINE_V2_STORE_PROFILE": "true",
    "ENGINE_V2_BUILDER_AOV_BUNDLE": "true",
    "ENGINE_V2_AOV_THRESHOLD_FROM_DATA": "true",
    "ENGINE_V2_OBSERVED_EFFECT_AOV_BUNDLE": "true",
    "ENGINE_V2_OBSERVED_ELIGIBILITY_GATE": "true",
    "VERTICAL_MODE": "beauty",
    "WINDOW_POLICY": "auto",
}
PLAY = "aov_lift_via_threshold_bundle"
with tempfile.TemporaryDirectory() as td:
    out_dir = Path(td) / "probe"
    r = run_scenario("healthy_beauty_240d", out_dir, env_overrides=env, timeout_sec=300)
    print("RC:", r.returncode)
    if r.returncode != 0:
        print(r.stderr[-1200:])
    run = json.loads((out_dir / "receipts" / "engine_run.json").read_text())
    print("Top-level keys:", list(run.keys()))
    print(f"considered_truncated_count: {run.get('considered_truncated_count')}")
    for key in ("recommendations","considered","watching","held","abstained","experiments","recommended_experiments","exploration","slate","held_under_abstain"):
        sec = run.get(key) or []
        if not isinstance(sec, list):
            continue
        ids = [(c.get("play_id"), c.get("reason_code")) for c in sec if isinstance(c, dict)]
        print(f"  SECTION {key} (len={len(sec)}): {ids}")
        for c in sec:
            if isinstance(c, dict) and c.get("play_id") == PLAY:
                print(f"\n--- FOUND IN {key} ---")
                print(json.dumps(c, indent=2)[:4000])
    # Recursive find
    def walk(node, path="root"):
        if isinstance(node, dict):
            if node.get("play_id") == PLAY:
                print(f"\n--- FOUND AT {path} ---")
                print(json.dumps(node, indent=2)[:6000])
            for k, v in node.items():
                walk(v, f"{path}.{k}")
        elif isinstance(node, list):
            for i, v in enumerate(node):
                walk(v, f"{path}[{i}]")
    walk(run)
    # Check receipts dir for all files
    rec_dir = out_dir / "receipts"
    print("\nReceipts files:")
    for p in sorted(rec_dir.glob("*")):
        print(f"  {p.name} {p.stat().st_size}b")
    for fname in ("v2_candidates.json","run_summary.json","v2_sizing_shadow.json","candidate_debug.json"):
        f = rec_dir / fname
        if f.exists():
            blob = f.read_text()
            has = PLAY in blob
            print(f"\n--- {fname}: contains PLAY={has} ---")
            if has:
                # walk and find
                try:
                    data = json.loads(blob)
                    def walk2(node, path="root"):
                        if isinstance(node, dict):
                            if any(isinstance(v, str) and PLAY in v for v in node.values()) or node.get("play_id") == PLAY:
                                print(f"  hit at {path}: {json.dumps(node, default=str)[:600]}")
                            for k, v in node.items():
                                walk2(v, f"{path}.{k}")
                        elif isinstance(node, list):
                            for i, v in enumerate(node):
                                walk2(v, f"{path}[{i}]")
                    walk2(data)
                except Exception as e:
                    print(f"  parse err: {e}")
    # Find all paths where string PLAY appears
    def walk_str(node, path="root"):
        if isinstance(node, dict):
            for k, v in node.items():
                if isinstance(v, str) and PLAY in v:
                    print(f"  STR at {path}.{k}: {v[:200]}")
                walk_str(v, f"{path}.{k}")
        elif isinstance(node, list):
            for i, v in enumerate(node):
                if isinstance(v, str) and PLAY in v:
                    print(f"  STR at {path}[{i}]: {v[:200]}")
                walk_str(v, f"{path}[{i}]")
    print("\nString appearances of PLAY:")
    walk_str(run)
    blob = json.dumps(run)
    print(f"\nContains 'aov_lift_via_threshold_bundle': {PLAY in blob}")
    print(f"Contains 'SIGNAL_INCONSISTENT_ACROSS_WINDOWS': {'SIGNAL_INCONSISTENT_ACROSS_WINDOWS' in blob}")
    print(f"Contains 'DOWNGRADE_JOINT_FAIL': {'DOWNGRADE_JOINT_FAIL' in blob}")
    print(f"Contains 'SIGNAL_JOINT_TEST_FAILED': {'SIGNAL_JOINT_TEST_FAILED' in blob}")
