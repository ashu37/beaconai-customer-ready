"""Tests for ``src.priors_loader`` (Milestone 6, T6.1).

The loader is the FIRST runtime consumer of ``config/priors.yaml``.
These tests pin:

- file load + cache (load once per process; ``clear_cache`` re-reads);
- malformed/missing-file fallback to ``{}``;
- scope-resolution order: subvertical > vertical > wildcard;
- typed :class:`PriorEntry` shape;
- conservative None-on-miss behavior.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

yaml = pytest.importorskip("yaml")

from src import priors_loader as PL


@pytest.fixture(autouse=True)
def _reset_cache():
    """Each test starts with an empty loader cache."""
    PL.clear_cache()
    yield
    PL.clear_cache()


# ---------------------------------------------------------------------------
# Real config: smoke
# ---------------------------------------------------------------------------


def test_default_yaml_loads():
    doc = PL.load_priors()
    assert isinstance(doc, dict)
    assert isinstance(doc.get("plays"), dict)
    assert "winback_21_45" in doc["plays"]


def test_schema_version_present():
    assert PL.schema_version() is not None


def test_get_prior_returns_typed_entry():
    e = PL.get_prior("winback_21_45", vertical="beauty", key="base_rate")
    assert e is not None
    assert isinstance(e, PL.PriorEntry)
    assert e.name == "base_rate"
    assert e.play_id == "winback_21_45"
    assert isinstance(e.value, float)
    assert isinstance(e.range_p10, float)
    assert isinstance(e.range_p90, float)
    assert e.range_p10 <= e.value <= e.range_p90
    assert e.source_class in {"observational", "causal", "expert"}


def test_get_prior_unknown_play_returns_none():
    assert PL.get_prior("nonexistent_play", vertical="beauty", key="base_rate") is None


def test_get_prior_unknown_key_returns_none():
    assert PL.get_prior("winback_21_45", vertical="beauty", key="nonexistent_key") is None


def test_list_priors_for_play_returns_raw_dicts():
    rows = PL.list_priors_for_play("winback_21_45")
    assert isinstance(rows, list)
    assert all(isinstance(r, dict) for r in rows)
    names = {r.get("name") for r in rows}
    assert "base_rate" in names
    assert "incrementality" in names


# ---------------------------------------------------------------------------
# Cache behavior
# ---------------------------------------------------------------------------


def test_load_priors_is_cached(monkeypatch):
    """Second call must re-use the cached doc, not re-read disk."""
    calls: list[Path] = []

    real_load = PL._load_yaml

    def _spy(p: Path):
        calls.append(p)
        return real_load(p)

    monkeypatch.setattr(PL, "_load_yaml", _spy)
    PL.clear_cache()
    d1 = PL.load_priors()
    d2 = PL.load_priors()
    assert d1 is d2  # same cached dict
    assert len(calls) == 1


def test_clear_cache_forces_reload(monkeypatch):
    calls: list[Path] = []
    real_load = PL._load_yaml

    def _spy(p: Path):
        calls.append(p)
        return real_load(p)

    monkeypatch.setattr(PL, "_load_yaml", _spy)
    PL.clear_cache()
    PL.load_priors()
    PL.clear_cache()
    PL.load_priors()
    assert len(calls) == 2


# ---------------------------------------------------------------------------
# Failure / fallback cases
# ---------------------------------------------------------------------------


def test_missing_file_returns_empty(tmp_path):
    bogus = tmp_path / "no_such.yaml"
    doc = PL.load_priors(bogus)
    assert doc == {}


def test_malformed_yaml_returns_empty(tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text("not: valid: yaml: at: all\n  - mixed:\n   indent\n", encoding="utf-8")
    PL.clear_cache()
    doc = PL.load_priors(bad)
    # YAML parser may or may not parse this; either way, loader must not raise.
    assert isinstance(doc, dict)


# ---------------------------------------------------------------------------
# Scope resolution: subvertical > vertical > wildcard
# ---------------------------------------------------------------------------


def _write_yaml(p: Path, body: str) -> None:
    p.write_text(body, encoding="utf-8")


def test_scope_subvertical_wins_over_vertical(tmp_path):
    p = tmp_path / "priors.yaml"
    _write_yaml(p, """
schema_version: "1.0.0"
last_reviewed: "2026-05-02"
plays:
  test_play:
    - name: base_rate
      value: 0.10
      range_p10: 0.05
      range_p90: 0.15
      source_class: expert
      last_updated: "2026-05-02"
      applies_to: { vertical: "*" }
    - name: base_rate
      value: 0.20
      range_p10: 0.10
      range_p90: 0.30
      source_class: expert
      last_updated: "2026-05-02"
      applies_to: { vertical: beauty }
    - name: base_rate
      value: 0.40
      range_p10: 0.30
      range_p90: 0.50
      source_class: causal
      last_updated: "2026-05-02"
      applies_to: { vertical: beauty, subvertical: skincare }
""")
    PL.clear_cache()
    e = PL.get_prior("test_play", vertical="beauty", subvertical="skincare", key="base_rate", path=p)
    assert e is not None
    assert e.value == 0.40  # subvertical-specific entry
    assert e.source_class == "causal"


def test_scope_vertical_wins_over_wildcard(tmp_path):
    p = tmp_path / "priors.yaml"
    _write_yaml(p, """
schema_version: "1.0.0"
last_reviewed: "2026-05-02"
plays:
  test_play:
    - name: base_rate
      value: 0.10
      range_p10: 0.05
      range_p90: 0.15
      source_class: expert
      last_updated: "2026-05-02"
      applies_to: { vertical: "*" }
    - name: base_rate
      value: 0.25
      range_p10: 0.15
      range_p90: 0.35
      source_class: expert
      last_updated: "2026-05-02"
      applies_to: { vertical: beauty }
""")
    PL.clear_cache()
    e = PL.get_prior("test_play", vertical="beauty", key="base_rate", path=p)
    assert e is not None
    assert e.value == 0.25


def test_scope_wildcard_used_when_no_vertical_match(tmp_path):
    p = tmp_path / "priors.yaml"
    _write_yaml(p, """
schema_version: "1.0.0"
last_reviewed: "2026-05-02"
plays:
  test_play:
    - name: base_rate
      value: 0.10
      range_p10: 0.05
      range_p90: 0.15
      source_class: expert
      last_updated: "2026-05-02"
      applies_to: { vertical: "*" }
""")
    PL.clear_cache()
    e = PL.get_prior("test_play", vertical="supplements", key="base_rate", path=p)
    assert e is not None
    assert e.value == 0.10


def test_scope_no_match_returns_none(tmp_path):
    p = tmp_path / "priors.yaml"
    _write_yaml(p, """
schema_version: "1.0.0"
last_reviewed: "2026-05-02"
plays:
  test_play:
    - name: base_rate
      value: 0.10
      range_p10: 0.05
      range_p90: 0.15
      source_class: expert
      last_updated: "2026-05-02"
      applies_to: { vertical: beauty }
""")
    PL.clear_cache()
    e = PL.get_prior("test_play", vertical="supplements", key="base_rate", path=p)
    assert e is None


def test_malformed_entry_is_skipped(tmp_path):
    p = tmp_path / "priors.yaml"
    _write_yaml(p, """
schema_version: "1.0.0"
last_reviewed: "2026-05-02"
plays:
  test_play:
    - name: base_rate
      value: not_a_number
      range_p10: 0.05
      range_p90: 0.15
      source_class: expert
      last_updated: "2026-05-02"
      applies_to: { vertical: beauty }
""")
    PL.clear_cache()
    e = PL.get_prior("test_play", vertical="beauty", key="base_rate", path=p)
    # Bad entry is skipped, no other entries exist -> None.
    assert e is None
