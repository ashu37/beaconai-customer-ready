"""S8-T0 atomic re-pin helper for KI-NEW-K Beauty Beta envelope re-fit.

Re-pins Beauty + Supplements pinned briefings after the YAML edit on
`discount_dependency_hygiene.base_rate.beauty` +
`replenishment_due.base_rate.beauty` (Beta(0.66, 29.34) -> Beta(1.32, 58.68)
at effective_n=60).

Expectation:
- Beauty re-pins: `discount_dependency_hygiene` blend posterior shifts by a
  small amount; store dominates at observed_n=224K so revenue_range bounds
  move by tens of basis points at most, but JSON bytes change due to
  changed prior metadata (effective_n=60).
- Supplements UNCHANGED: no supplements `discount_dependency_hygiene.base_rate`
  entry exists; `replenishment_due` is dormant on Beauty per KI-NEW-G
  honest-dormancy and supplements has no entry either.
"""
from __future__ import annotations

import hashlib
import shutil
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tests.synthetic_harness import run_scenario  # noqa: E402

ENV_BEAUTY = {
    "ENGINE_V2_OUTPUT": "true",
    "ENGINE_V2_DECIDE": "true",
    "ENGINE_V2_SLATE": "true",
    "ENGINE_V2_SIZING": "true",
    "VERTICAL_MODE": "beauty",
    "WINDOW_POLICY": "auto",
}
ENV_SUPP = dict(ENV_BEAUTY)
ENV_SUPP["VERTICAL_MODE"] = "supplements"


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _run(scenario: str, env: dict) -> Path:
    td = Path(tempfile.mkdtemp(prefix=f"{scenario}_"))
    res = run_scenario(scenario, td / "out", env_overrides=env, timeout_sec=300)
    if res.returncode != 0:
        print(f"FAIL {scenario}: {res.stderr[-800:]}")
        sys.exit(1)
    return td / "out" / "briefings" / f"{scenario}_briefing.html"


def main() -> int:
    fix_dir = REPO_ROOT / "tests" / "fixtures" / "synthetic_slate"

    b_old = fix_dir / "healthy_beauty_240d_briefing.html"
    b_old_sha = _sha(b_old)
    b_new = _run("healthy_beauty_240d", ENV_BEAUTY)
    b_new_sha = hashlib.sha256(b_new.read_bytes()).hexdigest()
    if b_old_sha == b_new_sha:
        print(f"Beauty UNCHANGED sha={b_new_sha}")
    else:
        shutil.copyfile(b_new, b_old)
        print(f"Beauty RE-PINNED old={b_old_sha} new={b_new_sha}")

    s_old = fix_dir / "healthy_supplements_240d_briefing.html"
    s_old_sha = _sha(s_old)
    s_new = _run("healthy_supplements_240d", ENV_SUPP)
    s_new_sha = hashlib.sha256(s_new.read_bytes()).hexdigest()
    if s_old_sha == s_new_sha:
        print(f"Supplements UNCHANGED sha={s_new_sha}")
    else:
        shutil.copyfile(s_new, s_old)
        print(f"Supplements RE-PINNED old={s_old_sha} new={s_new_sha}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
