"""S7.6-C2 inert-on-synthetic-fixtures probe.

Wrap ``apply_guardrails_to_injected`` to log:
  - injected card play_ids
  - demoted card play_ids
  - input vs output rec list

Expect zero demotions on both Beauty and Supplements pinned fixtures
(DS verdict afb1fb2f81eebf88f, 2026-05-22). Idempotence: second invocation
yields same set.

Read-only — does not mutate src/.
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
    "WINDOW_POLICY": "auto",
})

import src.guardrails as _gr  # noqa: E402

_real_helper = _gr.apply_guardrails_to_injected

_records: list[dict] = []
_call_counter = {"n": 0}

def _wrap_helper(engine_run, **kwargs):
    _call_counter["n"] += 1
    pre_set = set(kwargs.get("pre_injection_play_ids") or set())
    pre_recs = [str(getattr(c, "play_id", "")) for c in (engine_run.recommendations or [])]
    injected = [p for p in pre_recs if p not in pre_set]
    result = _real_helper(engine_run, **kwargs)
    post_recs = [str(getattr(c, "play_id", "")) for c in (result.recommendations or [])]
    demoted = [p for p in pre_recs if p not in post_recs]
    rec = {
        "call_n": _call_counter["n"],
        "pre_injection_set_size": len(pre_set),
        "pre_recs": pre_recs,
        "injected": injected,
        "post_recs": post_recs,
        "demoted": demoted,
    }
    _records.append(rec)
    print(f"[C2-HELPER call#{_call_counter['n']}] "
          f"injected={injected} demoted={demoted}")
    # Idempotence: invoke helper a second time and verify same result.
    if not demoted:
        result2 = _real_helper(result, **{**kwargs,
                                          "pre_injection_play_ids": pre_set})
        post2 = [str(getattr(c, "play_id", "")) for c in (result2.recommendations or [])]
        idem = (post2 == post_recs)
        print(f"[C2-HELPER call#{_call_counter['n']}] idempotent={idem}")
        rec["idempotent"] = idem
    return result

_gr.apply_guardrails_to_injected = _wrap_helper
# Patch main.py's lazy-bound symbol path (it does `from .guardrails import apply_guardrails_to_injected as _apply_guardrails_to_injected` inside the function body, so the wrap above suffices).

from src.main import main as _engine_main  # noqa: E402

def _run(vertical: str, orders_csv: str, inventory_csv: str, brand: str):
    print(f"\n{'='*70}\nVERTICAL={vertical} BRAND={brand}\n{'='*70}")
    os.environ["VERTICAL_MODE"] = vertical
    with tempfile.TemporaryDirectory() as td:
        out_dir = Path(td) / f"probe_{brand}"
        out_dir.mkdir(parents=True, exist_ok=True)
        argv = [
            "src.main",
            "--orders", orders_csv,
            "--inventory", inventory_csv,
            "--brand", brand,
            "--out", str(out_dir),
        ]
        sys.argv = argv
        try:
            _engine_main()
        except SystemExit as e:
            print(f"SystemExit: {e}")

fixture_dir = REPO_ROOT / "tests" / "fixtures" / "synthetic"

_records.clear()
_call_counter["n"] = 0
_run("beauty",
     str(fixture_dir / "healthy_beauty_240d_orders.csv"),
     str(fixture_dir / "healthy_beauty_240d_inventory.csv"),
     "healthy_beauty_240d")
beauty_records = list(_records)

_records.clear()
_call_counter["n"] = 0
_run("supplements",
     str(fixture_dir / "healthy_supplements_240d_orders.csv"),
     str(fixture_dir / "healthy_supplements_240d_inventory.csv"),
     "healthy_supplements_240d")
sup_records = list(_records)

print("\n" + "="*70)
print("C2 HELPER INERT-PROBE SUMMARY")
print("="*70)
print(f"\nBeauty: helper called {len(beauty_records)} time(s)")
for r in beauty_records:
    print(f"  call#{r['call_n']}: injected={r['injected']} demoted={r['demoted']} "
          f"idempotent={r.get('idempotent')}")

print(f"\nSupplements: helper called {len(sup_records)} time(s)")
for r in sup_records:
    print(f"  call#{r['call_n']}: injected={r['injected']} demoted={r['demoted']} "
          f"idempotent={r.get('idempotent')}")

total_demoted = sum(len(r["demoted"]) for r in beauty_records + sup_records)
print(f"\nTOTAL DEMOTIONS ACROSS BOTH FIXTURES: {total_demoted}")
print(f"VERDICT: {'INERT (PASS)' if total_demoted == 0 else 'NON-INERT (ESCALATE)'}")
