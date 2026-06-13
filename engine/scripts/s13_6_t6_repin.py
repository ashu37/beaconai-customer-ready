"""S13.6-T6 engine_run.json re-pin helper.

Per founder lock-in #3 (2026-05-30) + Option C founder approval
(2026-05-31): captures the post-T6 ``engine_run.json`` SHA on the 5
pinned ``tests/fixtures/synthetic_scenarios.yaml`` fixtures after:

- Adding the ``MechanismType(str, Enum)`` closed enum (10 members)
  and ``MechanismIntent`` typed atom in ``src/engine_run.py`` per
  DS §(d).
- Adding ``PlayCard.mechanism_intent: Optional[MechanismIntent]`` as
  a new additive field (Pivot 2 reaffirmation; narration agents read
  the typed atom from the contract).
- Retyping ``RejectedPlay.mechanism: Optional[str]`` ->
  ``Optional[MechanismIntent]`` (completion of T1a prose-strip
  discipline; the field T1a missed by accident).
- Wiring the new ``src/decide._build_mechanism_intent`` helper into:
  * the 4 RejectedPlay producer sites in ``src/decide.py``
    (assemble_considered / WINDOW_DISAGREEMENT / PRIOR_UNVALIDATED /
    SIGNAL_INCONSISTENT_ACROSS_WINDOWS),
  * the 2 prior-anchored PlayCard producer sites in
    ``src/measurement_builder.py``,
  * the experiment PlayCard producer in ``src/decide.py``, and
  * the legacy adapter PlayCard producer in
    ``src/engine_run_adapter.py``.

JSON shape changes (post-T6):

    PlayCard:    + "mechanism_intent": {"type": "...", "parameters": {...}}
                 (null today on legacy plays whose play_id has no entry
                 in ``_PLAY_ID_TO_MECHANISM_TYPE``)
    RejectedPlay: "mechanism": "<prose>"   ->
                  "mechanism": {"type": "...", "parameters": {...}}
                  (null on unmapped play_ids; previously YAML prose)

The SHA on every emitted PlayCard + every emitted RejectedPlay WILL
move. Re-pin via this script + the ledger entry at
``tests/fixtures/pinned_sha_ledger.json``.

Modeled on ``scripts/s13_6_t5_repin.py``.

Caveat (carried forward from S13-T3.5 and T1a/T1b/T2/T3/T4/T5):
``engine_run.json`` contains wall-clock ``fit_timestamp`` values from
the S10-S12 ML ModelCards, so the SHAs printed here record the
at-commit moment only. The load-bearing post-T6 test gates are the
dataclass + enum introspection + AST sweep + emitted-JSON shape
assertion in ``tests/test_s13_6_t6_mechanism_intent_atom.py`` — NOT
this ledger.
"""
from __future__ import annotations

import hashlib
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tests.synthetic_harness import run_scenario  # noqa: E402

ENV_BASE = {
    "ENGINE_V2_OUTPUT": "true",
    "ENGINE_V2_DECIDE": "true",
    "ENGINE_V2_SLATE": "true",
    "ENGINE_V2_SIZING": "true",
    "WINDOW_POLICY": "auto",
}

SCENARIOS = [
    ("healthy_beauty_240d", "beauty"),
    ("healthy_supplements_240d", "supplements"),
    ("small_store_240d", "beauty"),
    ("cold_start_45d", "beauty"),
    ("healthy_beauty_low_inventory_240d", "beauty"),
]


def main() -> int:
    print("S13.6-T6 engine_run.json SHA re-pin")
    print("=" * 60)
    for scenario, vertical in SCENARIOS:
        env = dict(ENV_BASE)
        env["VERTICAL_MODE"] = vertical
        with tempfile.TemporaryDirectory(prefix=f"{scenario}_") as td:
            res = run_scenario(
                scenario, Path(td) / "out",
                env_overrides=env, timeout_sec=300,
            )
            if res.returncode != 0:
                print(f"FAIL {scenario}: {res.stderr[-500:]}")
                continue
            er_path = res.engine_run_json_path
            if not er_path.exists():
                print(f"{scenario}: engine_run.json NOT PRODUCED")
                continue
            sha = hashlib.sha256(er_path.read_bytes()).hexdigest()
            print(f"  {scenario}: {sha}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
