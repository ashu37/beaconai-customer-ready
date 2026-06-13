"""Empirical wiring trace for S7.6 observed-effect CLI path.

Read-only probe: monkey-patches the discount_dependency_hygiene helper
and the builder seam to print, at each layer, what kwargs/values flow.
Does NOT modify src/. Run from repo root with the same env vars as the
failing CLI command.

Usage:
    ENGINE_V2_OBSERVED_EFFECT_DISCOUNT_HYGIENE=true \
    ENGINE_V2_BUILDER_DISCOUNT_HYGIENE=true \
    ENGINE_V2_OUTPUT=true ENGINE_V2_DECIDE=true ENGINE_V2_SLATE=true \
    python scripts/s7_6_cli_wiring_trace.py
"""
from __future__ import annotations

import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from src import measurement_builder as mb  # noqa: E402
from src import engine_run as er  # noqa: E402


_orig_helper = mb.compute_discount_hygiene_observed_effect
_orig_builder = mb.build_prior_anchored_play_card
_orig_card_init = er.PlayCard.__init__


def _patched_helper(orders_df, *a, vertical=None, **kw):
    print(f"[PROBE helper] CALLED vertical={vertical} orders_df_shape={getattr(orders_df,'shape',None)}")
    res = _orig_helper(orders_df, *a, vertical=vertical, **kw)
    try:
        primary, agreement = res
        print(f"[PROBE helper] RETURNED primary.k={getattr(primary,'k',None)} primary.n={getattr(primary,'n',None)} agreement_sign_count={getattr(agreement,'sign_agreement_count',None)}")
    except Exception as e:
        print(f"[PROBE helper] return unpack err: {e}")
    return res


def _patched_builder(cand, aligned, **kw):
    pid = getattr(cand, "play_id", None)
    if pid == "discount_dependency_hygiene":
        print(
            f"[PROBE builder] CALLED play_id={pid} "
            f"observed_discount_hygiene_enabled={kw.get('observed_discount_hygiene_enabled')} "
            f"orders_df_is_None={kw.get('orders_df') is None} "
            f"vertical={kw.get('vertical')}"
        )
    card = _orig_builder(cand, aligned, **kw)
    if pid == "discount_dependency_hygiene" and card is not None:
        rr = getattr(card, "revenue_range", None)
        drivers = (rr.drivers if rr else []) or []
        bp = next((d for d in drivers if isinstance(d, dict) and d.get("name") == "blend_provenance"), None)
        meas = getattr(card, "measurement", None)
        print(f"[PROBE builder] OUT measurement.observed_effect={getattr(meas,'observed_effect',None)}")
        print(f"[PROBE builder] OUT measurement.n={getattr(meas,'n',None)}")
        print(f"[PROBE builder] OUT measurement.consistency_across_windows={getattr(meas,'consistency_across_windows',None)}")
        print(f"[PROBE builder] OUT measurement.p_internal={getattr(meas,'p_internal',None)}")
        if bp:
            print(f"[PROBE builder] OUT blend_provenance.observed_k={bp.get('observed_k')} observed_n={bp.get('observed_n')}")
            print(f"[PROBE builder] OUT blend_provenance.observed_sign_agreement_count={bp.get('observed_sign_agreement_count')}")
            print(f"[PROBE builder] OUT blend_provenance.observed_windows.keys={list((bp.get('observed_windows') or {}).keys())}")
            l28 = (bp.get("observed_windows") or {}).get("L28") or {}
            print(f"[PROBE builder] OUT blend_provenance.observed_windows.L28={l28}")
        else:
            print("[PROBE builder] OUT NO blend_provenance driver on revenue_range.drivers")
        # Confirm: does PlayCard schema HAVE a top-level blend_provenance field?
        print(f"[PROBE builder] PlayCard has attr 'blend_provenance'? {hasattr(card, 'blend_provenance')}")
    return card


mb.compute_discount_hygiene_observed_effect = _patched_helper
mb.build_prior_anchored_play_card = _patched_builder

# Also re-bind in main.py's import surface
from src import main as _main  # noqa: E402
# main.py imports lazily inside the injection block, so patching the
# measurement_builder module attribute is sufficient.

# Run the engine on Beauty fixture
from pathlib import Path  # noqa: E402

os.environ.setdefault("ENGINE_V2_BUILDER_DISCOUNT_HYGIENE", "true")
os.environ.setdefault("ENGINE_V2_OBSERVED_EFFECT_DISCOUNT_HYGIENE", "true")
os.environ.setdefault("ENGINE_V2_DECIDE", "true")
os.environ.setdefault("ENGINE_V2_OUTPUT", "true")
os.environ.setdefault("ENGINE_V2_SLATE", "true")

# Try to find Beauty fixture CSV path
candidates = [
    Path(REPO) / "data" / "beauty" / "orders.csv",
    Path(REPO) / "tests" / "fixtures" / "beauty",
]
print("[PROBE setup] fixture candidates exist:")
for c in candidates:
    print(f"  {c} -> exists={c.exists()}")

# Use main.main() with sys.argv
sys.argv = ["main.py", "--brand", "beauty", "--out", "/tmp/s76_probe_out"]
try:
    _main.main()
except SystemExit:
    pass
except Exception as e:
    import traceback
    print(f"[PROBE setup] main.main() raised: {e}")
    traceback.print_exc()
