"""Milestone 3 integration: ENGINE_V2_SHADOW=true must:

1. produce ``receipts/v2_candidates.json`` for the fixture run, AND
2. leave the legacy outputs byte-identical to the M0 golden tree.

Default mode (flag unset / false) MUST also produce byte-identical
output relative to goldens. That is already covered by
``tests/test_golden_diff.py``; this test specifically pairs the
shadow-mode invocation with the same byte-identity check so a
regression in the shadow-mode wiring is caught at PR time.
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURE_PATH = REPO_ROOT / "tests" / "fixtures" / "merchants.yaml"
GOLDEN_ROOT = REPO_ROOT / "tests" / "golden"

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def _load_merchants():
    spec = yaml.safe_load(FIXTURE_PATH.read_text())
    return spec.get("merchants", []) or []


def _merchant_ids():
    if not FIXTURE_PATH.exists():
        return []
    return [m["id"] for m in _load_merchants()]


@pytest.fixture(scope="module")
def freeze_module():
    script_path = REPO_ROOT / "scripts" / "freeze_golden.py"
    spec = importlib.util.spec_from_file_location("freeze_golden", script_path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.parametrize("merchant_id", _merchant_ids())
def test_shadow_mode_preserves_goldens_and_writes_receipt(freeze_module, merchant_id):
    fm = freeze_module
    merchants = {m["id"]: m for m in _load_merchants()}
    merchant = merchants[merchant_id]
    brand = merchant.get("brand") or merchant_id
    golden_dir = GOLDEN_ROOT / merchant_id
    if not golden_dir.exists():
        pytest.skip(f"no golden tree for {merchant_id}")

    os.chdir(REPO_ROOT)
    prev = os.environ.get("ENGINE_V2_SHADOW")
    # M4b T4b.5: goldens reflect both M4b flags ON. Shadow-mode wiring must
    # preserve those goldens, so we set the same flag combo here.
    prev_nan = os.environ.get("STATS_NAN_FOR_HARDCODED")
    prev_evc = os.environ.get("EVIDENCE_CLASS_ENFORCED")
    os.environ["ENGINE_V2_SHADOW"] = "true"
    os.environ["STATS_NAN_FOR_HARDCODED"] = "true"
    os.environ["EVIDENCE_CLASS_ENFORCED"] = "true"
    try:
        with tempfile.TemporaryDirectory(prefix=f"beaconai_shadow_{merchant_id}_") as tmp:
            run_dir = Path(tmp)
            fm._run_engine(merchant, run_dir)

            # 1) v2_candidates.json must exist and parse.
            v2_path = run_dir / "receipts" / "v2_candidates.json"
            assert v2_path.exists(), f"shadow mode did not produce {v2_path}"
            payload = json.loads(v2_path.read_text(encoding="utf-8"))
            assert isinstance(payload, list)
            # Sanity: every entry has the slim contract.
            for entry in payload:
                assert "play_id" in entry
                assert "audience_size" in entry
                assert "segment_definition" in entry
                assert "cold_start" in entry
                assert "audience_overlap" in entry
                assert "preliminary_rejection_reason" in entry
                # Forbidden statistical fields must NOT appear.
                for forbidden in (
                    "p_value",
                    "p",
                    "q",
                    "ci_low",
                    "ci_high",
                    "score",
                    "rank",
                    "expected_$",
                    "revenue",
                    "measured_effect",
                    "confidence",
                ):
                    assert forbidden not in entry, f"{forbidden} leaked into v2 receipt"

            # 2) Legacy outputs must remain byte-identical to golden.
            with tempfile.TemporaryDirectory(prefix=f"beaconai_shadow_check_{merchant_id}_") as tmp2:
                check_dest = Path(tmp2) / merchant_id
                fm._capture_outputs(run_dir, brand, check_dest)
                golden_files = {
                    p.relative_to(golden_dir) for p in golden_dir.rglob("*") if p.is_file()
                }
                check_files = {
                    p.relative_to(check_dest) for p in check_dest.rglob("*") if p.is_file()
                }
                assert golden_files == check_files, (
                    f"shadow mode produced different file set than golden for {merchant_id}: "
                    f"only_golden={sorted(str(p) for p in (golden_files - check_files))}, "
                    f"only_check={sorted(str(p) for p in (check_files - golden_files))}"
                )
                diffs = []
                for rel in sorted(golden_files):
                    d = fm._diff_paths(golden_dir / rel, check_dest / rel)
                    if d:
                        diffs.append(d)
                assert not diffs, (
                    f"shadow mode drifted golden output for {merchant_id}.\n"
                    + "\n".join(diffs)[:4000]
                )
    finally:
        if prev is None:
            os.environ.pop("ENGINE_V2_SHADOW", None)
        else:
            os.environ["ENGINE_V2_SHADOW"] = prev
        for var, prior in (
            ("STATS_NAN_FOR_HARDCODED", prev_nan),
            ("EVIDENCE_CLASS_ENFORCED", prev_evc),
        ):
            if prior is None:
                os.environ.pop(var, None)
            else:
                os.environ[var] = prior
