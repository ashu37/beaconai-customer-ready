"""Deep probe: intercept build_prior_anchored_play_card to see candidate state under full engine.

Patches src.measurement_builder.build_prior_anchored_play_card to log
incoming candidate for aov_lift_via_threshold_bundle and return whatever
the real impl returns.
"""
from __future__ import annotations
import json
import os
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# Set env BEFORE importing engine modules
os.environ.update({
    "ENGINE_V2_OUTPUT": "true",
    "ENGINE_V2_DECIDE": "true",
    "ENGINE_V2_SLATE": "true",
    "ENGINE_V2_SIZING": "true",
    "ENGINE_V2_BUILDER_AOV_BUNDLE": "true",
    "ENGINE_V2_AOV_THRESHOLD_FROM_DATA": "true",
    "WINDOW_POLICY": "auto",
    "VERTICAL_MODE": "beauty",
})

from src import measurement_builder as mb  # noqa: E402

PLAY_ID = "aov_lift_via_threshold_bundle"
_real_card = mb.build_prior_anchored_play_card
_real_recs = mb.build_prior_anchored_recommendations

def _wrapped_card(candidate, aligned, **kwargs):
    pid = str(getattr(candidate, "play_id", "") or "")
    if pid == PLAY_ID:
        print(f"\n[PROBE] build_prior_anchored_play_card called for {pid}")
        print(f"  audience_size              : {getattr(candidate, 'audience_size', None)}")
        print(f"  preliminary_rejection_reason: {getattr(candidate, 'preliminary_rejection_reason', None)}")
        print(f"  threshold_source           : {getattr(candidate, 'threshold_source', None)}")
        print(f"  segment_definition         : {str(getattr(candidate, 'segment_definition', ''))[:120]}")
        print(f"  kwargs.vertical            : {kwargs.get('vertical')}")
    result = _real_card(candidate, aligned, **kwargs)
    if pid == PLAY_ID:
        print(f"  -> returned: {type(result).__name__ if result else None}")
    return result

def _wrapped_recs(candidates, aligned, **kwargs):
    cands = list(candidates or [])
    matching = [c for c in cands if str(getattr(c, "play_id", "")) == PLAY_ID]
    print(f"\n[PROBE] build_prior_anchored_recommendations called, allowed={kwargs.get('allowed_play_ids')}")
    print(f"  total candidates           : {len(cands)}")
    print(f"  matching {PLAY_ID} cands   : {len(matching)}")
    for c in matching:
        print(f"    cand audience_size: {getattr(c, 'audience_size', None)}")
        print(f"    cand prelim_reason: {getattr(c, 'preliminary_rejection_reason', None)}")
        print(f"    cand threshold_src: {getattr(c, 'threshold_source', None)}")
    result = _real_recs(candidates, aligned, **kwargs)
    print(f"  -> emitted {len(result)} cards: {[getattr(c, 'play_id', None) for c in result]}")
    return result

mb.build_prior_anchored_play_card = _wrapped_card
mb.build_prior_anchored_recommendations = _wrapped_recs

# Also wrap main's import
import src.main as smain  # noqa: E402
# main.py uses `from .measurement_builder import build_prior_anchored_recommendations as _build_prior_anchored_t3b`
# inside a function, so our patched mb attr will be picked up.

from tests.synthetic_harness import run_scenario  # noqa: E402

with tempfile.TemporaryDirectory() as td:
    out_dir = Path(td) / "probe"
    env = dict(os.environ)
    result = run_scenario("healthy_beauty_240d", out_dir, env_overrides=env, timeout_sec=300)
    print(f"\n[harness] returncode: {result.returncode}")
    if result.returncode != 0:
        print(result.stderr[-2000:])
    else:
        # The harness runs in a subprocess, so our patches don't apply.
        # Print stdout if anything captured.
        print("[harness] stdout tail:")
        print(result.stdout[-1500:])
