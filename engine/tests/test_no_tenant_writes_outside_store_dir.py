"""B-4/S-1 CI guard: tenant-data artifacts must live under data/<store_id>/.

Mitigation for the "missed call site" risk row in the implementation
plan. Runs the engine in an isolated tmpdir and asserts no
``recommended_history.json`` is written outside ``data/<store_id>/``.

(``actions_log.json`` is written into the per-run ``receipts_dir`` —
already per-run-isolated, not under ``data/`` — so it is not part of the
per-store directory contract; we only assert that it does NOT appear
under a top-level ``data/`` path.)
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

# Tenant-data artifact filenames whose location is contractually scoped
# to ``data/<store_id>/`` after B-4/S-1.
SCOPED_ARTIFACTS = {"recommended_history.json"}

# Filenames that must NEVER appear directly under ``data/`` (only inside
# per-store subdirs or per-run receipts_dirs).
NEVER_AT_DATA_ROOT = {"recommended_history.json", "actions_log.json"}


def _have_synthetic_csv() -> Path | None:
    candidates = [
        REPO_ROOT / "tests" / "fixtures" / "synthetic" / "healthy_beauty_240d_orders.csv",
        REPO_ROOT / "data" / "test_data.csv",
        REPO_ROOT / "data" / "shopify_orders_micro_20250826_202615.csv",
    ]
    for c in candidates:
        if c.exists():
            return c
    return None


@pytest.mark.skipif(
    _have_synthetic_csv() is None,
    reason="restored at S13.6-T1a (Pivot 2 strip regex cleanup)",
)
def test_no_tenant_writes_outside_per_store_dir():
    orders_csv = _have_synthetic_csv()
    assert orders_csv is not None

    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        out_dir = td_path / "out"
        out_dir.mkdir()

        env = dict(os.environ)
        env["PYTHONPATH"] = (
            f"{REPO_ROOT}{os.pathsep}{env.get('PYTHONPATH', '')}"
        )
        env["STORE_ID"] = "guard_store"
        env["OUTCOME_LOG_ENABLED"] = "true"
        env.pop("OUTCOME_LOG_PATH", None)

        cmd = [
            sys.executable,
            "-m",
            "src.main",
            "--orders",
            str(orders_csv.resolve()),
            "--brand",
            "guard_store",
            "--out",
            str(out_dir),
        ]
        proc = subprocess.run(
            cmd,
            env=env,
            cwd=str(td_path),
            capture_output=True,
            text=True,
            timeout=300,
        )
        assert proc.returncode == 0, (
            f"engine run failed rc={proc.returncode} "
            f"stderr={proc.stderr[-500:]}"
        )

        data_root = td_path / "data"
        assert data_root.exists(), "engine never created data/ under cwd"

        # 1) Direct contents of data/ must never include the scoped names
        # at the top level — they must always be one level deeper.
        top_level_files = {p.name for p in data_root.iterdir() if p.is_file()}
        leaked_at_root = NEVER_AT_DATA_ROOT & top_level_files
        assert not leaked_at_root, (
            f"tenant artifact leaked to data/ root: {leaked_at_root}; "
            f"all top-level entries: {sorted(p.name for p in data_root.iterdir())}"
        )

        # 2) Every occurrence of a scoped artifact must live under
        # data/<store_id>/ — i.e. relative path of form ``<some_id>/<name>``
        # (one segment of store_id between data/ and the file).
        store_dir_pattern = re.compile(r"^[a-z0-9_-]+$")
        for name in SCOPED_ARTIFACTS:
            for hit in data_root.rglob(name):
                rel = hit.relative_to(data_root).parts
                assert len(rel) == 2, (
                    f"{name} at unexpected depth: data/{'/'.join(rel)}; "
                    f"expected exactly data/<store_id>/{name}"
                )
                assert store_dir_pattern.match(rel[0]), (
                    f"{name} parent dir is not a sanitized store_id: "
                    f"{rel[0]!r}"
                )
