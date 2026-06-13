"""Smoke test: resolve small_sm via the manifest pointer and narrate it
through the MOCK client. Runs WITHOUT an ANTHROPIC_API_KEY, no network.

Pins the manifest-pointer resolution contract (handoff_architecture.md
§2a): the snapshot is located via (manifest_dir / artifacts.engine_run),
NEVER a hardcoded path, NEVER the receipts/ mirror.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.mcp.narration.run_locator import (
    RunLocatorError,
    load_run,
    resolve_snapshot_path,
)
from src.mcp.narration.server import narrate_card_payload, narrate_run_payload

_STORE = "small_sm"
_RUN = "f119c98b-1108-4dd6-bd6f-d12f6e133899"
_DATA_ROOT = Path(__file__).resolve().parents[1] / "data"

_pytestmark_skip = not (_DATA_ROOT / _STORE / "runs" / _RUN / "manifest.json").is_file()


pytestmark = pytest.mark.skipif(
    _pytestmark_skip,
    reason="canonical small_sm fixture not present on disk",
)


def test_manifest_pointer_resolves_one_level_up():
    manifest = _DATA_ROOT / _STORE / "runs" / _RUN / "manifest.json"
    snapshot = resolve_snapshot_path(manifest)
    # Snapshot is a sibling FILE of the run directory, one level up.
    assert snapshot == (_DATA_ROOT / _STORE / "runs" / f"{_RUN}.json").resolve()
    assert snapshot.is_file()
    # It is NOT the receipts mirror.
    assert "receipts" not in str(snapshot)


def test_resolve_rejects_receipts_pointer(tmp_path):
    bad = tmp_path / "manifest.json"
    bad.write_text('{"artifacts": {"engine_run": "../receipts/engine_run.json"}}')
    with pytest.raises(RunLocatorError):
        resolve_snapshot_path(bad)


def test_load_and_parse_run():
    resolved = load_run(_DATA_ROOT, _STORE, _RUN)
    assert resolved.store_id == _STORE
    assert resolved.run_id == _RUN
    assert len(resolved.engine_run.recommendations) == 1
    assert resolved.engine_run.recommendations[0].play_id == "bestseller_amplify"


def test_narrate_run_through_mock_is_lock_clean():
    out = narrate_run_payload(_STORE, _RUN, data_root=str(_DATA_ROOT))
    assert out["llm_mode"] == "mock"
    assert out["run_id"] == _RUN
    assert len(out["cards"]) == 1
    card = out["cards"][0]
    assert card["play_id"] == "bestseller_amplify"
    assert card["guard_violations"] == []
    assert card["used_fallback"] is False
    # L8: the fixture's revenue_range.source is None (NOT BLEND), so NO
    # dollar figure may appear for this card.
    blob = card["play_thesis"] + card["what_we_d_send"] + card["evidence_summary"]
    assert "$" not in blob


def test_narrate_single_card():
    out = narrate_card_payload(
        _STORE, _RUN, "bestseller_amplify", data_root=str(_DATA_ROOT)
    )
    assert out["card"]["play_id"] == "bestseller_amplify"
    assert out["card"]["guard_violations"] == []


def test_narrate_missing_card():
    out = narrate_card_payload(_STORE, _RUN, "no_such_play", data_root=str(_DATA_ROOT))
    assert "error" in out
