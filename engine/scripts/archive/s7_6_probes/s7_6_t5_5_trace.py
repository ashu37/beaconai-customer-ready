"""Trace WHERE aov_bundle gets dropped with T5.5 ON.

Monkeypatch decide() to dump state at each routing step.
"""
import json, sys, tempfile
from pathlib import Path
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from tests.synthetic_harness import run_scenario
import os

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
    "ENGINE_DEBUG_AOV": "1",
}
PLAY = "aov_lift_via_threshold_bundle"

# Patch decide module
import src.decide as dec_mod
orig_route_elig = dec_mod._route_observed_eligibility_holds
orig_route_pv = dec_mod._route_prior_unvalidated_holds
orig_route_wd = dec_mod._route_window_disagreement_holds

def wrap(name, fn):
    def w(*a, **kw):
        recs = list(a[0] or [])
        ids_in = [c.play_id for c in recs]
        out = fn(*a, **kw)
        kept_ids = [c.play_id for c in out[0]]
        ref_ids = [r.play_id for r in out[1]]
        print(f"[{name}] in={ids_in} kept={kept_ids} refused={ref_ids}")
        return out
    return w

dec_mod._route_observed_eligibility_holds = wrap("ELIG", orig_route_elig)
dec_mod._route_prior_unvalidated_holds = wrap("PRIOR_UNVAL", orig_route_pv)
dec_mod._route_window_disagreement_holds = wrap("WIN_DIS", orig_route_wd)

orig_decide = dec_mod.decide
def patched_decide(engine_run, **kw):
    incoming_ids = [c.play_id for c in (engine_run.recommendations or [])]
    cons_ids = [r.play_id for r in (engine_run.considered or [])]
    print(f"[INPUT] recs={incoming_ids}")
    print(f"[INPUT] considered_in={cons_ids}")
    out = orig_decide(engine_run, **kw)
    out_rec_ids = [c.play_id for c in (out.recommendations or [])]
    out_cons = [(r.play_id, getattr(r, 'reason_code', None)) for r in (out.considered or [])]
    print(f"[OUTPUT] recs={out_rec_ids}")
    print(f"[OUTPUT] considered={out_cons}")
    return out
dec_mod.decide = patched_decide

with tempfile.TemporaryDirectory() as td:
    out_dir = Path(td) / "probe"
    # Inline run, since run_scenario is subprocess (won't see monkeypatch).
    # Use direct main invocation.
    from src.main import run_engine_for_scenario
