"""In-process probe with monkeypatch on the measurement_builder.

Calls main.run() directly so our patches apply.
"""
from __future__ import annotations
import os
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

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

from src import audience_builders as _ab  # noqa: E402
_real_aov_cand = _ab.aov_lift_via_threshold_bundle_candidates

def _wrapped_aov_cand(g, aligned, cfg=None, **kw):
    print(f"\n[PROBE-AOV-CAND] cfg flag={('ENGINE_V2_AOV_THRESHOLD_FROM_DATA' in (cfg or {}))} value={(cfg or {}).get('ENGINE_V2_AOV_THRESHOLD_FROM_DATA')} VERTICAL={(cfg or {}).get('VERTICAL_MODE')}")
    print(f"  cfg keys subset: {[k for k in (cfg or {}).keys() if 'AOV' in k or 'VERTICAL' in k or 'THRESHOLD' in k]}")
    res = _real_aov_cand(g, aligned, cfg, **kw)
    print(f"  result a_size={res.audience_size} reason={res.preliminary_rejection_reason} src={getattr(res, 'threshold_source', None)}")
    return res

_ab.aov_lift_via_threshold_bundle_candidates = _wrapped_aov_cand
_ab.BUILDERS["audience.aov_lift_via_threshold_bundle"] = _wrapped_aov_cand

from src import measurement_builder as mb  # noqa: E402

PLAY_ID = "aov_lift_via_threshold_bundle"
_real_card = mb.build_prior_anchored_play_card
_real_recs = mb.build_prior_anchored_recommendations


def _wrapped_card(candidate, aligned, **kwargs):
    pid = str(getattr(candidate, "play_id", "") or "")
    if pid == PLAY_ID:
        print(f"\n[PROBE-CARD] {pid}")
        print(f"  audience_size              : {getattr(candidate, 'audience_size', None)}")
        print(f"  preliminary_rejection_reason: {getattr(candidate, 'preliminary_rejection_reason', None)}")
        print(f"  threshold_source           : {getattr(candidate, 'threshold_source', None)}")
        print(f"  vertical kwarg             : {kwargs.get('vertical')}")
        print(f"  subvertical kwarg          : {kwargs.get('subvertical')}")
    result = _real_card(candidate, aligned, **kwargs)
    if pid == PLAY_ID:
        print(f"  -> {type(result).__name__ if result else 'None'}")
        if result is not None:
            print(f"  -> revenue_range.suppressed: {getattr(getattr(result, 'revenue_range', None), 'suppressed', None)}")
    return result


def _wrapped_recs(candidates, aligned, **kwargs):
    cands = list(candidates or [])
    matching = [c for c in cands if str(getattr(c, "play_id", "")) == PLAY_ID]
    print(f"\n[PROBE-RECS] allowed={kwargs.get('allowed_play_ids')}, total cands={len(cands)}, matching={len(matching)}")
    for c in matching:
        print(f"  cand a_size={getattr(c, 'audience_size', None)} reason={getattr(c, 'preliminary_rejection_reason', None)} src={getattr(c, 'threshold_source', None)}")
    result = _real_recs(candidates, aligned, **kwargs)
    print(f"  emitted={len(result)} ids={[getattr(c, 'play_id', None) for c in result]}")
    return result


# Also probe detect_candidates / populate_considered
mb.build_prior_anchored_play_card = _wrapped_card
mb.build_prior_anchored_recommendations = _wrapped_recs

# Probe populate_considered to see if/why it doesn't emit
from src import decide as p52  # noqa: E402
_real_pop = p52.populate_considered_from_candidates


def _wrapped_pop(engine_run, candidates, **kwargs):
    cands = list(candidates or [])
    matching = [c for c in cands if str(getattr(c, "play_id", "")) == PLAY_ID]
    print(f"\n[PROBE-POP-CONS] total={len(cands)} matching {PLAY_ID}={len(matching)}")
    for c in matching:
        print(f"  cand a_size={getattr(c, 'audience_size', None)} reason={getattr(c, 'preliminary_rejection_reason', None)}")
    pre_cons_ids = [getattr(c, 'play_id', None) for c in (engine_run.considered or [])]
    pre_rec_ids = [getattr(c, 'play_id', None) for c in (engine_run.recommendations or [])]
    print(f"  pre considered: {pre_cons_ids}")
    print(f"  pre recs      : {pre_rec_ids}")
    res = _real_pop(engine_run, candidates, **kwargs)
    post_cons_ids = [getattr(c, 'play_id', None) for c in (res.considered or [])]
    post_rec_ids = [getattr(c, 'play_id', None) for c in (res.recommendations or [])]
    print(f"  post considered: {post_cons_ids}")
    print(f"  post recs      : {post_rec_ids}")
    return res


p52.populate_considered_from_candidates = _wrapped_pop

# Wrap decide() as well
_real_decide = p52.decide

def _wrapped_decide(engine_run, **kwargs):
    pre_rec_ids = [getattr(c, 'play_id', None) for c in (engine_run.recommendations or [])]
    pre_cons_ids = [getattr(c, 'play_id', None) for c in (engine_run.considered or [])]
    print(f"\n[PROBE-DECIDE-PRE] recs={pre_rec_ids}")
    print(f"[PROBE-DECIDE-PRE] cons={pre_cons_ids}")
    res = _real_decide(engine_run, **kwargs)
    post_rec_ids = [getattr(c, 'play_id', None) for c in (res.recommendations or [])]
    post_cons_ids = [getattr(c, 'play_id', None) for c in (res.considered or [])]
    print(f"[PROBE-DECIDE-POST] recs={post_rec_ids}")
    print(f"[PROBE-DECIDE-POST] cons={post_cons_ids}")
    return res

p52.decide = _wrapped_decide

# Also wrap materiality re-gate (it's used by main via direct import)
from src import guardrails as _gr
_real_gm = _gr.gate_materiality

def _wrapped_gm(card, monthly_revenue, **kwargs):
    pid = str(getattr(card, "play_id", "") or "")
    rej = _real_gm(card, monthly_revenue, **kwargs)
    if pid == PLAY_ID:
        print(f"\n[PROBE-MATERIALITY] {pid} -> rejected={rej is not None}")
        if rej is not None:
            print(f"  reason: {getattr(rej, 'reason_code', None)} text: {getattr(rej, 'reason_text', None)[:120]}")
    return rej

_gr.gate_materiality = _wrapped_gm


# Now run main
import argparse  # noqa: E402
from src.main import main as _engine_main  # noqa: E402

with tempfile.TemporaryDirectory() as td:
    out_dir = Path(td) / "probe"
    out_dir.mkdir(parents=True, exist_ok=True)
    fixture_dir = REPO_ROOT / "tests" / "fixtures" / "synthetic"
    orders = fixture_dir / "healthy_beauty_240d_orders.csv"
    products = fixture_dir / "healthy_beauty_240d_products.csv"
    customers = fixture_dir / "healthy_beauty_240d_customers.csv"

    # Build argv
    argv = [
        "src.main",
        "--orders", str(orders),
        "--brand", "healthy_beauty_240d",
        "--out", str(out_dir),
    ]
    sys.argv = argv
    try:
        _engine_main()
    except SystemExit as e:
        print(f"SystemExit: {e}")
    except Exception as e:
        import traceback
        traceback.print_exc()
