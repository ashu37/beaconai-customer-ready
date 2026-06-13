"""B-4/S-1: store_id resolver + per-store directory unit tests."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.store_id import (
    FALLBACK_STORE_ID,
    ensure_store_dir,
    migrate_legacy_recommended_history,
    resolve_store_id,
    store_data_dir,
)


class TestResolveStoreId:
    def test_env_override_wins(self, tmp_path: Path):
        csv = tmp_path / "merchant_x" / "orders.csv"
        csv.parent.mkdir(parents=True)
        csv.write_text("")
        sid = resolve_store_id(
            csv, brand_arg="brand_y", env={"STORE_ID": "from_env"}
        )
        assert sid == "from_env"

    def test_brand_arg_when_no_env(self, tmp_path: Path):
        csv = tmp_path / "merchant_x" / "orders.csv"
        csv.parent.mkdir(parents=True)
        csv.write_text("")
        sid = resolve_store_id(csv, brand_arg="brand_y", env={})
        assert sid == "brand_y"

    def test_basename_fallback(self, tmp_path: Path):
        csv = tmp_path / "MerchantX" / "orders.csv"
        csv.parent.mkdir(parents=True)
        csv.write_text("")
        sid = resolve_store_id(csv, brand_arg=None, env={})
        assert sid == "merchantx"

    def test_unknown_when_nothing_resolves(self):
        sid = resolve_store_id(orders_csv_path=None, brand_arg=None, env={})
        assert sid == FALLBACK_STORE_ID

    def test_sanitizes_unsafe_chars(self):
        sid = resolve_store_id(env={"STORE_ID": "Hostile/../Path Name!!"})
        assert "/" not in sid
        assert ".." not in sid
        assert " " not in sid
        # Whitelist enforced
        assert all(c.isalnum() or c in {"-", "_"} for c in sid)

    def test_lowercase(self):
        sid = resolve_store_id(env={"STORE_ID": "BrandABC"})
        assert sid == "brandabc"

    def test_empty_env_falls_through(self, tmp_path: Path):
        csv = tmp_path / "fromcsv" / "x.csv"
        csv.parent.mkdir(parents=True)
        csv.write_text("")
        sid = resolve_store_id(csv, brand_arg="", env={"STORE_ID": ""})
        assert sid == "fromcsv"


class TestStoreDataDir:
    def test_layout(self, tmp_path: Path):
        p = store_data_dir("alpha", base=tmp_path)
        assert p == tmp_path / "alpha"
        assert not p.exists()  # store_data_dir does not create

    def test_ensure_creates(self, tmp_path: Path):
        p = ensure_store_dir("beta", base=tmp_path)
        assert p.exists()
        assert p.is_dir()


class TestMigration:
    def test_no_legacy_no_op(self, tmp_path: Path):
        status = migrate_legacy_recommended_history("s1", base=tmp_path)
        assert status["status"] == "no_legacy"

    def test_copies_with_attribution(self, tmp_path: Path):
        legacy = tmp_path / "recommended_history.json"
        legacy.write_text('[{"play_id": "x"}]')
        status = migrate_legacy_recommended_history("s1", base=tmp_path)
        assert status["status"] == "migrated"
        dest = tmp_path / "s1" / "recommended_history.json"
        assert dest.exists()
        assert json.loads(dest.read_text()) == [{"play_id": "x"}]
        sidecar = tmp_path / "s1" / ".migration.json"
        assert sidecar.exists()
        meta = json.loads(sidecar.read_text())
        assert meta["source_path"].endswith("recommended_history.json")
        assert meta["store_id"] == "s1"
        assert meta["source_sha256"]
        # Legacy NOT deleted (D-3 full-wipe-only).
        assert legacy.exists()

    def test_idempotent(self, tmp_path: Path):
        legacy = tmp_path / "recommended_history.json"
        legacy.write_text("[]")
        first = migrate_legacy_recommended_history("s1", base=tmp_path)
        assert first["status"] == "migrated"
        second = migrate_legacy_recommended_history("s1", base=tmp_path)
        assert second["status"] == "dest_exists"
