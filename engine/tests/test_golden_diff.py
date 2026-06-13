"""Milestone 0 regression test: every fixture merchant's engine output must
match its frozen golden tree under tests/golden/.

This test re-runs the engine end-to-end for each merchant in
tests/fixtures/merchants.yaml using the same normalization rules as
scripts/freeze_golden.py and asserts byte-equality against the committed
golden artifacts. Failures print a unified diff so the human reviewer can
decide whether the change is intentional (-> regenerate goldens via
`python scripts/freeze_golden.py --regenerate` and commit alongside a
justification) or a regression (-> revert/fix).

The test is intentionally heavy: it runs the full CSV -> HTML pipeline. If it
becomes painful in inner-loop dev, mark it with `pytest -m "not golden"` once
M1 introduces a marker; for now M0 keeps it in the default pytest target so
that any unintended drift is caught at PR time.
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURE_PATH = REPO_ROOT / "tests" / "fixtures" / "merchants.yaml"
GOLDEN_ROOT = REPO_ROOT / "tests" / "golden"

# Ensure repo root is importable.
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def _load_merchants():
    spec = yaml.safe_load(FIXTURE_PATH.read_text())
    return spec.get("merchants", []) or []


def _merchant_ids():
    """Pytest parametrize source. Skips gracefully if fixtures/golden missing."""
    if not FIXTURE_PATH.exists():
        return []
    return [m["id"] for m in _load_merchants()]


@pytest.fixture(scope="module")
def freeze_module():
    """Import the freeze script as a module so tests share its helpers."""
    import importlib.util

    script_path = REPO_ROOT / "scripts" / "freeze_golden.py"
    spec = importlib.util.spec_from_file_location("freeze_golden", script_path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.parametrize("merchant_id", _merchant_ids())
def test_golden_matches(freeze_module, merchant_id, monkeypatch):
    """Re-run engine for one merchant; diff every captured file vs golden.

    Milestone 4b re-baseline: the committed golden tree reflects engine
    output with both M4b flags ON (``STATS_NAN_FOR_HARDCODED=true`` and
    ``EVIDENCE_CLASS_ENFORCED=true``). The test forces those env vars on
    so the regression catches drift in the new canonical state, regardless
    of any local ``.env`` overrides. The legacy flag-off path is still
    runnable end-to-end (verified by smoke runs) but produces the M4a
    baseline output rather than the M4b goldens — that is the documented
    plan T4b.5 outcome.
    """
    fm = freeze_module
    merchants = {m["id"]: m for m in _load_merchants()}
    merchant = merchants[merchant_id]
    brand = merchant.get("brand") or merchant_id
    golden_dir = GOLDEN_ROOT / merchant_id

    if not golden_dir.exists():
        pytest.skip(
            f"No golden tree for {merchant_id} -- "
            f"run `python scripts/freeze_golden.py --regenerate` to create it."
        )

    # M4b T4b.5: force the M4b flag-on state for the regression baseline.
    monkeypatch.setenv("STATS_NAN_FOR_HARDCODED", "true")
    monkeypatch.setenv("EVIDENCE_CLASS_ENFORCED", "true")

    # Run engine + capture into a temp dir; compare against committed golden.
    os.chdir(REPO_ROOT)
    with tempfile.TemporaryDirectory(prefix=f"beaconai_test_{merchant_id}_") as tmp:
        run_dir = Path(tmp)
        fm._run_engine(merchant, run_dir)
        with tempfile.TemporaryDirectory(prefix=f"beaconai_check_{merchant_id}_") as tmp2:
            check_dest = Path(tmp2) / merchant_id
            fm._capture_outputs(run_dir, brand, check_dest)

            golden_files = {
                p.relative_to(golden_dir)
                for p in golden_dir.rglob("*")
                if p.is_file()
            }
            check_files = {
                p.relative_to(check_dest)
                for p in check_dest.rglob("*")
                if p.is_file()
            }

            extra_in_check = check_files - golden_files
            extra_in_golden = golden_files - check_files
            assert not extra_in_check, (
                f"{merchant_id}: new output file(s) not in golden: "
                f"{sorted(str(p) for p in extra_in_check)}. "
                f"Either remove them or regenerate goldens."
            )
            assert not extra_in_golden, (
                f"{merchant_id}: golden has file(s) the run did not produce: "
                f"{sorted(str(p) for p in extra_in_golden)}. "
                f"Either restore the writer or regenerate goldens."
            )

            diffs = []
            for rel in sorted(golden_files):
                d = fm._diff_paths(golden_dir / rel, check_dest / rel)
                if d:
                    diffs.append(d)
            if diffs:
                joined = "\n".join(diffs)
                # Truncate to keep pytest output readable.
                preview = joined if len(joined) <= 16000 else (joined[:16000] + "\n... [truncated]")
                pytest.fail(
                    f"Golden drift for {merchant_id}.\n"
                    f"To accept these changes intentionally, run:\n"
                    f"    python scripts/freeze_golden.py --regenerate --merchant {merchant_id}\n"
                    f"and commit the regenerated tests/golden/ tree with a\n"
                    f"justification line citing the milestone ticket.\n\n"
                    f"--- diff ---\n{preview}"
                )
