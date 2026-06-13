"""Force N=10 per-SKU floor (no store profile cell override) to isolate
whether Beauty's per-SKU repeater distribution clears N=10 at all.
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

ENV = {
    "ENGINE_V2_OUTPUT": "true",
    "ENGINE_V2_DECIDE": "true",
    "ENGINE_V2_SLATE": "true",
    "ENGINE_V2_SIZING": "true",
    "ENGINE_V2_PRIORS_VALIDATION": "true",
    "VERTICAL_MODE": "beauty",
    "WINDOW_POLICY": "auto",
    "ENGINE_V2_OBSERVED_EFFECT_REPLENISHMENT": "true",
    "ENGINE_V2_BUILDER_REPLENISHMENT_DUE": "true",
    "ENGINE_V2_STORE_PROFILE": "false",
    "MIN_N_REPLENISHMENT_DUE_PER_SKU": "10",
    "MIN_N_REPLENISHMENT_DUE": "0",
}


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "p"
        r = run_scenario("healthy_beauty_240d", out, env_overrides=ENV, timeout_sec=300)
        if r.returncode != 0:
            print(r.stderr[-1500:])
            return 1
        run = json.loads((out / "receipts" / "engine_run.json").read_text())
        for sec in ("recommendations", "considered", "experiments", "watching"):
            for it in (run.get(sec) or []):
                if "replen" in str(it.get("play_id", "")).lower():
                    print(f"{sec}: {it.get('play_id')}")
                    print(f"  audience_size={it.get('audience_size')}")
                    print(f"  reason_code={it.get('reason_code')}")
                    print(f"  audience_definition={it.get('audience_definition')}")
                    print(f"  preliminary_rejection_reason={it.get('preliminary_rejection_reason')}")

        # also try N=3
    print("\n--- now N=3 (very loose) ---")
    env2 = dict(ENV)
    env2["MIN_N_REPLENISHMENT_DUE_PER_SKU"] = "3"
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "p"
        r = run_scenario("healthy_beauty_240d", out, env_overrides=env2, timeout_sec=300)
        run = json.loads((out / "receipts" / "engine_run.json").read_text())
        for sec in ("recommendations", "considered"):
            for it in (run.get(sec) or []):
                if "replen" in str(it.get("play_id", "")).lower():
                    print(f"{sec}: {it.get('play_id')} aud_size={it.get('audience_size')} reason={it.get('reason_code')} def={it.get('audience_definition')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
