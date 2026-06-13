"""Tests for Sprint 1 Ticket B-7 — Hard-refuse non-supported verticals.

Acceptance fixtures (per implementation-manager-post-6b-restructured-plan.md
Section 1, Ticket B-7):

1. Synthetic apparel CSV -> ABSTAIN_HARD with data_quality_flag =
   VERTICAL_NOT_SUPPORTED. No slate, no recommendations, no
   recommended_experiments. The briefing renders only a refusal panel
   (here: we assert the briefing render is skipped entirely; main.run
   returns early after writing engine_run.json).

2. Unit test: vertical_mode="food_bev" -> ABSTAIN_HARD with the typed flag.

3. Unit test (regression guard): vertical_mode in
   {"beauty", "supplements", "mixed"} -> no refusal.

4. Loader-level test: a priors.yaml that contains an "apparel:" block at
   the top level (in vertical_mode position) -> loader raises ConfigError
   with a message naming "apparel".

5. Frozen-contract test:
   assert _ALL_VERTICALS == frozenset({"beauty", "supplements", "mixed"}).

Hard constraints honored:
- engine_run.json schema is reused (data_quality_flags is the existing slot).
- M0 Beauty pinned fixture is byte-identical (no Beauty path touched).
- Trust contract preserved (no fabricated p/CI/projections).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Optional

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

yaml = pytest.importorskip("yaml")

from src import priors_loader as PL
from src.engine_run import DataQualityFlag, DecisionState
from src.play_registry import _ALL_VERTICALS
from src.vertical_guard import (
    MERCHANT_FACING_REFUSAL_COPY,
    SUPPORTED_VERTICALS,
    build_vertical_refusal_engine_run,
    is_supported,
)


# ---------------------------------------------------------------------------
# Acceptance test 5: frozen-contract on _ALL_VERTICALS
# ---------------------------------------------------------------------------


def test_all_verticals_frozen_contract():
    """The supported vertical set is hard-locked at {beauty, supplements, mixed}.

    Any future PR that adds a vertical breaks this test, forcing a
    founder-level scope decision (per B-7 / D-8).
    """

    assert _ALL_VERTICALS == frozenset({"beauty", "supplements", "mixed"})
    # The vertical_guard re-export must be identity-equal to the registry
    # set (single source of truth).
    assert SUPPORTED_VERTICALS is _ALL_VERTICALS


# ---------------------------------------------------------------------------
# Acceptance test 2: vertical_mode="food_bev" -> ABSTAIN_HARD with typed flag
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "vertical_mode",
    ["food_bev", "apparel", "home", "wellness", "FOOD_BEV", "Apparel"],
)
def test_unsupported_vertical_builds_abstain_hard(vertical_mode: str):
    """Any vertical_mode outside the supported set is refused.

    Casing variants are normalized before comparison.
    """

    assert is_supported(vertical_mode) is False

    er = build_vertical_refusal_engine_run(
        store_id="test_store", vertical_mode=vertical_mode
    )
    assert er.abstain.state == DecisionState.ABSTAIN_HARD
    assert DataQualityFlag.VERTICAL_NOT_SUPPORTED in er.data_quality_flags
    assert er.recommendations == []
    assert er.recommended_experiments == []
    assert er.considered == []
    assert er.watching == []

    # Round-trip the typed flag through the JSON serializer.
    payload = er.to_dict()
    assert payload["abstain"]["state"] == "abstain_hard"
    # S13.6-T1a: payload["abstain"]["reason"] stripped per Pivot 2.
    assert payload["data_quality_flags"] == ["vertical_not_supported"]
    assert payload["recommendations"] == []
    assert payload["recommended_experiments"] == []
    assert payload["considered"] == []
    assert payload["watching"] == []


def test_none_or_empty_vertical_mode_is_refused():
    """Unresolved vertical_mode is refused (NOT silently treated as 'mixed').

    Per the priors-loader Addendum 3 framing: ``mixed`` is a literal
    beauty+supplements blend, not an unknown-vertical fallback.
    """

    for v in (None, "", "   "):
        assert is_supported(v) is False


# ---------------------------------------------------------------------------
# Acceptance test 3: regression guard for the supported set
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "vertical_mode,expected",
    [
        ("beauty", True),
        ("supplements", True),
        ("mixed", True),
        ("Beauty", True),  # casing tolerated
        ("SUPPLEMENTS", True),
        ("MIXED", True),
        ("  beauty  ", True),  # whitespace tolerated
    ],
)
def test_supported_vertical_does_not_refuse(vertical_mode: str, expected: bool):
    """The three supported verticals must not be refused.

    Regression guard against an over-broad B-7 guard accidentally
    refusing Beauty / supplements / mixed runs.
    """

    assert is_supported(vertical_mode) is expected


# ---------------------------------------------------------------------------
# Acceptance test 4: priors.yaml with an apparel: top-level block raises
# ConfigError
# ---------------------------------------------------------------------------


def _write_yaml_fixture(tmp_path: Path, doc: dict) -> Path:
    p = tmp_path / "priors_fixture.yaml"
    p.write_text(yaml.safe_dump(doc), encoding="utf-8")
    return p


def test_priors_loader_raises_on_apparel_top_level_block(tmp_path: Path):
    """An apparel block in vertical-mode position must raise ConfigError.

    The error message must name the offending key so the YAML author
    can find and remove it.
    """

    fixture = _write_yaml_fixture(
        tmp_path,
        {
            "schema_version": "1.0.0",
            "plays": {},
            # In vertical-mode position alongside ``plays:``. Not supported.
            "apparel": {
                "base_rate": 0.05,
                "notes": "synthetic fixture; should be refused",
            },
        },
    )

    PL.clear_cache()
    try:
        with pytest.raises(PL.ConfigError) as excinfo:
            PL.load_priors(fixture)
        assert "apparel" in str(excinfo.value)
    finally:
        PL.clear_cache()


def test_priors_loader_raises_on_food_bev_top_level_block(tmp_path: Path):
    """food_bev / home / wellness are also refused permanently."""

    fixture = _write_yaml_fixture(
        tmp_path,
        {
            "schema_version": "1.0.0",
            "plays": {},
            "food_bev": {"base_rate": 0.04},
        },
    )

    PL.clear_cache()
    try:
        with pytest.raises(PL.ConfigError) as excinfo:
            PL.load_priors(fixture)
        assert "food_bev" in str(excinfo.value)
    finally:
        PL.clear_cache()


def test_priors_loader_accepts_supported_top_level_block(tmp_path: Path):
    """A top-level beauty/supplements/mixed block is permitted.

    Today the live YAML uses ``plays.<id>.applies_to.vertical`` for
    scope, NOT a top-level vertical block. But the loader must not
    refuse a future schema migration that DOES use top-level supported
    blocks. Regression guard.
    """

    fixture = _write_yaml_fixture(
        tmp_path,
        {
            "schema_version": "1.0.0",
            "plays": {},
            "beauty": {"notes": "ok"},
            "supplements": {"notes": "ok"},
            "mixed": {"notes": "ok"},
        },
    )

    PL.clear_cache()
    try:
        doc = PL.load_priors(fixture)
        assert "beauty" in doc
        assert "supplements" in doc
        assert "mixed" in doc
    finally:
        PL.clear_cache()


def test_priors_loader_real_yaml_still_loads_clean():
    """The shipped config/priors.yaml must continue to load without raising.

    Beta-blocker regression: if the B-7 validator over-refuses, every
    Beauty run on the real YAML breaks. The shipped YAML keeps
    vertical-mode information inside ``plays.<id>.applies_to.vertical``,
    so no top-level non-structural key should trip the guard.
    """

    PL.clear_cache()
    try:
        doc = PL.load_priors()
        assert isinstance(doc, dict)
        assert "plays" in doc
    finally:
        PL.clear_cache()


# ---------------------------------------------------------------------------
# Acceptance test 1: synthetic apparel CSV -> ABSTAIN_HARD via main.run
# ---------------------------------------------------------------------------


@pytest.fixture
def _apparel_csv(tmp_path: Path) -> Path:
    """Minimal synthetic Shopify-shaped orders CSV.

    Content is intentionally tiny — the B-7 guard must short-circuit
    BEFORE the feature builder ever runs, so the data shape is
    irrelevant. We still produce a parseable file in case a future
    refactor moves CSV parsing above the guard (which would be a bug
    we'd want a test to catch).
    """

    csv_path = tmp_path / "apparel_orders.csv"
    # Mimic a Shopify orders CSV header set seen elsewhere in the suite.
    csv_path.write_text(
        "Name,Email,Created at,Subtotal,Total Discount\n"
        "#1001,a@example.com,2025-01-01 10:00:00,50.00,0.00\n"
        "#1002,b@example.com,2025-01-02 10:00:00,75.00,5.00\n",
        encoding="utf-8",
    )
    return csv_path


def _set_vertical_mode(monkeypatch: pytest.MonkeyPatch, value: Optional[str]) -> None:
    """Monkeypatch ``src.utils.get_config`` to return a controlled cfg.

    The engine reads VERTICAL_MODE off ``cfg`` (a dict). Patching
    ``get_config`` is the least-invasive way to drive the guard from a
    test without touching .env files.
    """

    from src import main as _main

    def _fake_get_config():  # noqa: D401 — test helper
        if value is None:
            return {}
        return {"VERTICAL_MODE": value}

    monkeypatch.setattr(_main, "get_config", _fake_get_config)


def test_apparel_csv_short_circuits_to_abstain_hard(
    tmp_path: Path,
    _apparel_csv: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    """End-to-end: apparel CSV + VERTICAL_MODE=apparel -> ABSTAIN_HARD.

    Asserts:
    - main.run returns without raising.
    - receipts/engine_run.json exists and carries ABSTAIN_HARD with the
      VERTICAL_NOT_SUPPORTED flag.
    - no slate, no recommendations, no recommended_experiments.
    - briefing HTML is NOT rendered (the guard short-circuits before
      render_briefing). This is the "no slate, no briefing" half of the
      acceptance criterion.
    """

    from src import main as _main

    _set_vertical_mode(monkeypatch, "apparel")

    out_dir = tmp_path / "out"
    _main.run(
        csv_path=str(_apparel_csv),
        brand="apparel_test_store",
        out_dir=str(out_dir),
    )

    engine_run_path = out_dir / "receipts" / "engine_run.json"
    assert engine_run_path.exists(), "engine_run.json must be written on refusal"

    payload = json.loads(engine_run_path.read_text(encoding="utf-8"))
    assert payload["abstain"]["state"] == "abstain_hard"
    # S13.6-T1a: payload["abstain"]["reason"] stripped per Pivot 2.
    assert payload["data_quality_flags"] == ["vertical_not_supported"]
    assert payload["recommendations"] == []
    assert payload["recommended_experiments"] == []
    assert payload["considered"] == []

    # The briefing path must NOT be reached on refusal (we don't want a
    # normal slate with empty arrays).
    briefing_path = out_dir / "briefings" / "apparel_test_store_briefing.html"
    assert not briefing_path.exists(), (
        "Briefing HTML must not be rendered on a vertical hard-refuse run; "
        "the guard short-circuits before the briefing renderer runs."
    )


def test_supported_vertical_does_not_short_circuit(
    tmp_path: Path,
    _apparel_csv: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    """Negative regression: vertical_mode='beauty' must NOT short-circuit.

    We can't run the full Beauty pipeline here (the synthetic CSV is too
    small for compute_features). What we verify instead is that the
    guard's early-return path is NOT taken: the run progresses past the
    guard and any subsequent failure is from downstream code, not from
    the guard refusing.
    """

    from src import main as _main

    _set_vertical_mode(monkeypatch, "beauty")

    out_dir = tmp_path / "out"
    # We don't expect run() to complete cleanly on a 2-row synthetic
    # CSV — the feature builder needs more data — but we DO expect that
    # if it fails, it fails AFTER the guard, i.e. the guard's refusal
    # engine_run.json with VERTICAL_NOT_SUPPORTED is NEVER written.
    try:
        _main.run(
            csv_path=str(_apparel_csv),
            brand="beauty_test_store",
            out_dir=str(out_dir),
        )
    except Exception:
        # Downstream failures on a tiny synthetic CSV are tolerated for
        # the purposes of THIS test (which is about the guard, not the
        # full pipeline).
        pass

    engine_run_path = out_dir / "receipts" / "engine_run.json"
    if engine_run_path.exists():
        payload = json.loads(engine_run_path.read_text(encoding="utf-8"))
        # If anything wrote engine_run.json, it must NOT carry the
        # VERTICAL_NOT_SUPPORTED flag — that would prove the guard
        # mistakenly fired on a supported vertical.
        flags = payload.get("data_quality_flags") or []
        assert "vertical_not_supported" not in flags, (
            "Beauty must not be refused by the B-7 vertical guard."
        )
