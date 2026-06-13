"""S13.6-T5 — schema_version 1.0.0 -> 2.0.0 + CHANGELOG block pin.

Per founder lock-in #3 (2026-05-30): hard freeze at v2.0.0 after S13.6.
Subsequent additions require a major version bump + coordinated
narration / assembly agent update. Additive changes within ``2.x.x``
allowed; breaking changes -> ``3.0.0``.

This test pins three things:

1. ``EngineRun.schema_version`` default literal is ``"2.0.0"``.
2. The emitted ``engine_run.json`` payload on a fresh ``EngineRun()``
   serializes ``"schema_version": "2.0.0"``.
3. The CHANGELOG block at the top of ``src/engine_run.py`` is present
   and carries the load-bearing anchor phrases (sprint identifiers,
   freeze language, Q-S13-4 LOCK reference). Anchor-phrase containment
   only — full block text is intentionally NOT pinned (too brittle).
"""
from __future__ import annotations

import sys
from dataclasses import fields
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.engine_run import EngineRun  # noqa: E402


def test_engine_run_schema_version_default_literal_is_2_0_0() -> None:
    """Introspect ``dataclasses.fields(EngineRun)`` for the default."""
    fmap = {f.name: f for f in fields(EngineRun)}
    assert "schema_version" in fmap, (
        "EngineRun.schema_version field missing — contract regression."
    )
    default = fmap["schema_version"].default
    # S-FE-descriptive-distribution (FOUNDER-AUTHORIZED 2026-06-02): additive
    # 2.0.0 -> 2.1.0 within the 2.x.x freeze (founder lock-in #3 permits
    # additive 2.x changes; L-EV-19). The contract-freeze discipline holds —
    # this is an additive Optional field with a paired RULE-A null-reason.
    assert default == "2.1.0", (
        f"EngineRun.schema_version default literal must be '2.1.0' "
        f"(additive bump for Audience.descriptive_distribution per L-EV-19, "
        f"FOUNDER-AUTHORIZED 2026-06-02; additive within the founder lock-in #3 "
        f"2.x.x freeze). Got: {default!r}."
    )


def test_engine_run_emitted_json_carries_schema_version_2_0_0() -> None:
    """A freshly constructed ``EngineRun`` serializes
    ``"schema_version": "2.0.0"`` via ``to_dict()``."""
    er = EngineRun()
    payload = er.to_dict()
    # S-FE-descriptive-distribution: additive 2.0.0 -> 2.1.0 (L-EV-19).
    assert payload.get("schema_version") == "2.1.0", (
        f"EngineRun.to_dict() must emit schema_version='2.1.0'. "
        f"Got: {payload.get('schema_version')!r}."
    )


@pytest.mark.parametrize(
    "anchor",
    [
        # Version + freeze language:
        "v2.0.0",
        "S13.6-T5",
        "contract FREEZE",
        "Hard freeze",
        # Q-S13-4 LOCK reference (T2.5 / T4 preserved):
        "Q-S13-4 LOCK",
        # Sprint anchor list:
        "S13.6",
        "S13 close",
        # Founder lock-in identifier:
        "founder lock-in #3",
    ],
)
def test_engine_run_changelog_block_present_with_anchor_phrases(
    anchor: str,
) -> None:
    """Anchor-phrase containment check on the top-of-module CHANGELOG.

    Full block text intentionally NOT pinned — too brittle. We only
    pin the load-bearing identifiers that downstream agents
    (narration / assembly) need to rely on.
    """
    src_path = REPO_ROOT / "src" / "engine_run.py"
    text = src_path.read_text(encoding="utf-8")
    assert anchor in text, (
        f"CHANGELOG anchor phrase {anchor!r} missing from "
        f"src/engine_run.py top-of-module docstring. Did the T5 "
        f"CHANGELOG block get reverted or rewritten?"
    )
