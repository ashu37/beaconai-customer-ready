"""Read-only in-process probe — trace three Tier-B plays through the
supplements pipeline.

Targets: winback_dormant_cohort, cohort_journey_first_to_second,
aov_lift_via_threshold_bundle on the healthy_supplements_240d fixture.

Style mirrors scripts/s7_6_t7_5_inproc_probe.py — monkey-patch the
builder + measurement_builder + decide seams BEFORE importing
src.main, then invoke main() in-process and dump engine_run state.

No code in src/ is mutated. No commits.
"""
from __future__ import annotations
import os
import sys
import json
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# Use current defaults (utils.py DEFAULTS sets all the V2 builder flags ON
# per S7-T1.5/T2.5/T3.5/T4.5 closeouts). Only set the slate stack +
# vertical (supplements). Do NOT override builder flags.
os.environ.update({
    "ENGINE_V2_OUTPUT": "true",
    "ENGINE_V2_DECIDE": "true",
    "ENGINE_V2_SLATE": "true",
    "ENGINE_V2_SIZING": "true",
    "VERTICAL_MODE": "supplements",
    "WINDOW_POLICY": "auto",
})

TARGETS = {
    "winback_dormant_cohort",
    "cohort_journey_first_to_second",
    "aov_lift_via_threshold_bundle",
}

# ---------------------------------------------------------------------------
# Stage 1+2 — builder + phase5 candidate detection
# ---------------------------------------------------------------------------
from src import audience_builders as _ab  # noqa: E402

_builder_records: dict[str, dict] = {}

def _wrap_builder(name: str, real_fn):
    def _inner(g, aligned, cfg=None, **kw):
        try:
            res = real_fn(g, aligned, cfg, **kw)
        except TypeError:
            res = real_fn(g, aligned, cfg)
        rec = {
            "audience_size": getattr(res, "audience_size", None),
            "preliminary_rejection_reason": getattr(res, "preliminary_rejection_reason", None),
            "play_id": getattr(res, "play_id", None),
            "threshold_source": getattr(res, "threshold_source", None),
            "audience_definition_id": getattr(res, "audience_definition_id", None),
        }
        _builder_records[name] = rec
        print(f"[B1-BUILDER] {name}: a_size={rec['audience_size']} "
              f"reason={rec['preliminary_rejection_reason']} "
              f"src={rec['threshold_source']}")
        return res
    return _inner

for _name in ["winback_dormant_cohort", "cohort_journey_first_to_second",
              "aov_lift_via_threshold_bundle"]:
    _key = f"audience.{_name}"
    if _key in _ab.BUILDERS:
        _real = _ab.BUILDERS[_key]
        _ab.BUILDERS[_key] = _wrap_builder(_name, _real)

# ---------------------------------------------------------------------------
# Stage 2 (continued) — _detect_candidates result
# ---------------------------------------------------------------------------
from src import measurement_builder as mb  # noqa: E402
from src import detect as _detect_mod  # noqa: E402

_real_detect = _detect_mod.detect_candidates
_phase5_snapshot: list = []

def _wrap_detect(g, aligned, cfg, registry, **kwargs):
    res = _real_detect(g, aligned, cfg, registry, **kwargs)
    print(f"\n[B2-PHASE5-DETECT] total candidates={len(res)}")
    for c in res:
        pid = getattr(c, "play_id", None)
        if pid in TARGETS:
            _phase5_snapshot.append({
                "play_id": pid,
                "audience_size": getattr(c, "audience_size", None),
                "preliminary_rejection_reason": getattr(c, "preliminary_rejection_reason", None),
                "threshold_source": getattr(c, "threshold_source", None),
            })
            print(f"  [B2] {pid}: a_size={getattr(c, 'audience_size', None)} "
                  f"reason={getattr(c, 'preliminary_rejection_reason', None)}")
    seen_pids = {getattr(c, "play_id", None) for c in res}
    for t in TARGETS:
        if t not in seen_pids:
            print(f"  [B2-MISSING] {t} NOT in phase5 candidates")
    return res

_detect_mod.detect_candidates = _wrap_detect
# Re-bind the symbol main.py imports as `_detect_candidates` (from .detect import detect_candidates as _detect_candidates)
import src.main as _main_mod  # noqa: E402
_main_mod._detect_candidates = _wrap_detect  # in case it's already bound at module-import time we patch anyway; main does `from .detect import` inside the function body

# ---------------------------------------------------------------------------
# Stage 3+4 — priors + build_prior_anchored_play_card
# ---------------------------------------------------------------------------
_real_card = mb.build_prior_anchored_play_card

_card_records: dict[str, list[dict]] = {t: [] for t in TARGETS}

def _wrap_card(candidate, aligned, **kwargs):
    pid = str(getattr(candidate, "play_id", "") or "")
    if pid in TARGETS:
        print(f"\n[B4-CARDBUILD] {pid}")
        print(f"  vertical={kwargs.get('vertical')} subvertical={kwargs.get('subvertical')}")
        print(f"  a_size={getattr(candidate, 'audience_size', None)} "
              f"reason={getattr(candidate, 'preliminary_rejection_reason', None)}")
    result = _real_card(candidate, aligned, **kwargs)
    if pid in TARGETS:
        if result is None:
            print(f"  -> None (early-return)")
            _card_records[pid].append({"result": None})
        else:
            sup = getattr(getattr(result, "revenue_range", None), "suppressed", None)
            wbm = getattr(result, "would_be_measured_by", None)
            print(f"  -> PlayCard suppressed={sup} would_be_measured_by={wbm}")
            _card_records[pid].append({
                "result": "PlayCard",
                "suppressed": sup,
                "would_be_measured_by": str(wbm) if wbm is not None else None,
            })
    return result

mb.build_prior_anchored_play_card = _wrap_card

# Wrap get_prior so we can see prior resolution outcome per play
try:
    from src import priors as _priors_mod  # noqa: E402
    if hasattr(_priors_mod, "get_prior"):
        _real_get_prior = _priors_mod.get_prior

        def _wrap_get_prior(*args, **kwargs):
            res = _real_get_prior(*args, **kwargs)
            # args[0] is usually play_id
            pid = args[0] if args else kwargs.get("play_id")
            if isinstance(pid, str) and pid in TARGETS:
                vs = getattr(res, "validation_status", None) if res is not None else None
                bp = getattr(res, "blend_permitted", None) if res is not None else None
                print(f"[B3-PRIOR] {pid}: validation_status={vs} blend_permitted={bp} "
                      f"vertical={kwargs.get('vertical')} subvertical={kwargs.get('subvertical')}")
            return res
        _priors_mod.get_prior = _wrap_get_prior
except Exception as _e:
    print(f"[probe] priors wrap skipped: {_e}")

# ---------------------------------------------------------------------------
# Stage 5 — injection blocks at main.py:1320-1597
# Wrap build_prior_anchored_recommendations to log per-allowlist call.
# ---------------------------------------------------------------------------
_real_recs = mb.build_prior_anchored_recommendations

def _wrap_recs(candidates, aligned, **kwargs):
    allowed = kwargs.get("allowed_play_ids")
    cands = list(candidates or [])
    matching = [c for c in cands if str(getattr(c, "play_id", "")) in TARGETS]
    print(f"\n[B5-RECS] allowed={allowed} total={len(cands)} target_matching={len(matching)}")
    for c in matching:
        pid = getattr(c, "play_id", None)
        print(f"  in-cand {pid}: a_size={getattr(c, 'audience_size', None)} "
              f"reason={getattr(c, 'preliminary_rejection_reason', None)}")
    result = _real_recs(candidates, aligned, **kwargs)
    out_ids = [getattr(c, "play_id", None) for c in result]
    print(f"  emitted={len(result)} ids={out_ids}")
    return result

mb.build_prior_anchored_recommendations = _wrap_recs

# ---------------------------------------------------------------------------
# Stage 6/7 — decide() + considered routing
# ---------------------------------------------------------------------------
from src import decide as _dec  # noqa: E402

_real_decide = _dec.decide

def _wrap_decide(engine_run, **kwargs):
    pre_recs = [getattr(c, "play_id", None) for c in (engine_run.recommendations or [])]
    pre_cons = [getattr(c, "play_id", None) for c in (engine_run.considered or [])]
    print(f"\n[B6-DECIDE-PRE] recs={pre_recs}")
    print(f"[B6-DECIDE-PRE] considered={pre_cons}")
    res = _real_decide(engine_run, **kwargs)
    post_recs = [getattr(c, "play_id", None) for c in (res.recommendations or [])]
    post_cons = [getattr(c, "play_id", None) for c in (res.considered or [])]
    post_exp = [getattr(c, "play_id", None) for c in (res.recommended_experiments or [])]
    post_watch = [getattr(c, "metric_id", getattr(c, "play_id", None)) for c in (res.watching or [])]
    print(f"[B6-DECIDE-POST] recs={post_recs}")
    print(f"[B6-DECIDE-POST] considered={post_cons}")
    print(f"[B6-DECIDE-POST] recommended_experiments={post_exp}")
    print(f"[B6-DECIDE-POST] watching={post_watch}")
    return res

_dec.decide = _wrap_decide

# Wrap _route_prior_unvalidated_holds if present
if hasattr(_dec, "_route_prior_unvalidated_holds"):
    _real_route = _dec._route_prior_unvalidated_holds

    def _wrap_route(engine_run, *a, **k):
        pre = [getattr(c, "play_id", None) for c in (engine_run.considered or [])]
        res = _real_route(engine_run, *a, **k)
        post = [getattr(c, "play_id", None) for c in (res.considered or [])]
        added = [p for p in post if p not in pre]
        if any(p in TARGETS for p in added):
            print(f"[B7-ROUTE-PRIOR-UNVALIDATED] added to considered: {added}")
        return res

    _dec._route_prior_unvalidated_holds = _wrap_route

# ---------------------------------------------------------------------------
# Invoke main.run() in-process via argv
# ---------------------------------------------------------------------------
from src.main import main as _engine_main  # noqa: E402

with tempfile.TemporaryDirectory() as td:
    out_dir = Path(td) / "probe_sup"
    out_dir.mkdir(parents=True, exist_ok=True)
    fixture_dir = REPO_ROOT / "tests" / "fixtures" / "synthetic"
    orders = fixture_dir / "healthy_supplements_240d_orders.csv"
    inventory = fixture_dir / "healthy_supplements_240d_inventory.csv"

    argv = [
        "src.main",
        "--orders", str(orders),
        "--inventory", str(inventory),
        "--brand", "healthy_supplements_240d",
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

    # Now read engine_run.json and dump the final lists
    receipts = out_dir / "receipts" / "engine_run.json"
    if receipts.exists():
        data = json.loads(receipts.read_text(encoding="utf-8"))
        print("\n" + "=" * 70)
        print("FINAL engine_run.json SLATE DUMP (supplements)")
        print("=" * 70)
        recs = [p.get("play_id") for p in data.get("recommendations") or []]
        cons = [p.get("play_id") for p in data.get("considered") or []]
        exps = [p.get("play_id") for p in data.get("recommended_experiments") or []]
        watch = [p.get("metric_id") or p.get("play_id") for p in data.get("watching") or []]
        print(f"recommendations          : {recs}")
        print(f"considered               : {cons}")
        print(f"recommended_experiments  : {exps}")
        print(f"watching                 : {watch}")
        print(f"decision_state           : {data.get('decision_state')}")
        # Look for our targets specifically
        print("\nTARGET MEMBERSHIP:")
        for t in TARGETS:
            where = []
            if t in recs: where.append("recommendations")
            if t in cons: where.append("considered")
            if t in exps: where.append("recommended_experiments")
            if t in watch: where.append("watching")
            print(f"  {t}: {where or ['NOWHERE']}")
    else:
        print(f"[probe] receipts not written at {receipts}")
