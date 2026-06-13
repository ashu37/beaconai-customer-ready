"""Milestone 2 T2.5: Play registry sanity tests.

These tests guard the contract of ``src.play_registry``:

- Every legacy ``play_id`` ever emitted by ``_compute_candidates`` is
  represented in ``PLAYS``. Inventory comes from grepping
  ``play_id="..."`` literals out of ``src/action_engine.py`` (see the
  inventory list in this file's setup) and is the single forcing function
  that prevents M3+ from silently dropping a legacy play.

- ``PlayDef`` schema validation catches malformed entries.

- The three M2-T2.3 new entries (``first_to_second_purchase``,
  ``at_risk_repeat_buyer_rescue``, ``onsite_funnel_watch``) are present.

- Defaults agree with memory.md "Play classification" + PM Q3 doc:
  targeting plays declare no measurement_metric; bestseller_amplify
  requires_inventory; etc.

- Module imports cleanly and is leaf-level (no import-time dependency on
  ``src.action_engine``, which would create a registry/runtime cycle).

M2 is config-only; these tests do NOT exercise any runtime path.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.play_registry import (  # noqa: E402
    EVIDENCE_CLASSES,
    PLAYS,
    PlayDef,
    all_play_ids,
    get,
)


# ---------------------------------------------------------------------------
# Inventory of legacy emitted play_ids.
#
# This list is the M2 acceptance bar: every entry MUST be in ``PLAYS``.
# It was produced by grepping ``play_id="..."`` and ``"play_id": "..."`` in
# ``src/action_engine.py`` at the time of M2.
# ---------------------------------------------------------------------------

LEGACY_EMITTED_PLAY_IDS = {
    "winback_21_45",
    "bestseller_amplify",
    "discount_hygiene",
    "subscription_nudge",
    "routine_builder",
    "empty_bottle",
    "frequency_accelerator",
    "aov_momentum",
    "retention_mastery",
    "journey_optimization",
    "category_expansion",
}

# T2.3 new IDs (registry only; engine logic added in later milestones).
NEW_REGISTRY_IDS = {
    "first_to_second_purchase",
    "at_risk_repeat_buyer_rescue",
    "onsite_funnel_watch",
}


# ---------------------------------------------------------------------------
# T2.5 acceptance: every legacy emitted play_id is registered.
# ---------------------------------------------------------------------------


def test_every_legacy_emitted_play_id_is_registered():
    missing = LEGACY_EMITTED_PLAY_IDS - set(PLAYS.keys())
    assert not missing, (
        f"Legacy plays missing from registry: {sorted(missing)}. "
        f"Add a PlayDef to src/play_registry.PLAYS for each."
    )


def test_three_new_play_ids_registered():
    missing = NEW_REGISTRY_IDS - set(PLAYS.keys())
    assert not missing, f"M2-T2.3 new plays missing: {sorted(missing)}"


def test_play_count_at_least_legacy_plus_new():
    # 11 legacy + 3 new = 14 total minimum.
    assert len(PLAYS) >= len(LEGACY_EMITTED_PLAY_IDS) + len(NEW_REGISTRY_IDS)


# ---------------------------------------------------------------------------
# T2.5 acceptance: walk action_engine.py and assert each emitted id exists.
#
# This is the mechanical "registry sanity" forcing function. It re-greps
# the source code at test time so a future engineer who adds a new
# play_id="..." literal without registering it will fail this test.
# ---------------------------------------------------------------------------


def test_grep_action_engine_emitted_ids_match_registry():
    src_path = REPO_ROOT / "src" / "action_engine.py"
    src = src_path.read_text(encoding="utf-8")

    # Catch both kw-arg style (play_id="winback_21_45",) and dict-key style
    # ("play_id": "winback_21_45",). Both styles appear today.
    pattern = re.compile(r"""(?:^|\s)["']?play_id["']?\s*[=:]\s*["']([a-z0-9_]+)["']""")
    found = set(pattern.findall(src))

    # Any "id" we observed in source AND that looks like a real play
    # (lowercase, has underscores or is recognizable) must be registered.
    # Filter out any obvious test/placeholder values defensively.
    candidates = {pid for pid in found if pid and pid != "unknown"}

    missing = candidates - set(PLAYS.keys())
    assert not missing, (
        f"play_id literals in src/action_engine.py not registered in "
        f"PLAYS: {sorted(missing)}. Either add a PlayDef or remove the "
        f"emitter."
    )


# ---------------------------------------------------------------------------
# Schema validation per PlayDef.
# ---------------------------------------------------------------------------


def test_all_required_fields_populated():
    for pid, play in PLAYS.items():
        assert isinstance(play, PlayDef), pid
        assert play.play_id == pid, f"Registry key {pid!r} != PlayDef.play_id {play.play_id!r}"
        assert play.display_name, pid
        assert play.evidence_class_default in EVIDENCE_CLASSES, pid
        assert isinstance(play.requires_inventory, bool), pid
        assert play.audience_builder_ref, pid
        assert isinstance(play.prior_keys, list), pid


def test_targeting_plays_have_no_measurement_metric():
    for pid, play in PLAYS.items():
        if play.evidence_class_default == "targeting":
            assert play.measurement_metric is None, (
                f"Targeting play {pid!r} declares measurement_metric="
                f"{play.measurement_metric!r}; targeting plays must have None "
                f"per PM-Q2 hard rule (evidence_class==targeting => measurement is null)."
            )


def test_bestseller_amplify_requires_inventory():
    play = PLAYS["bestseller_amplify"]
    assert play.requires_inventory is True
    assert play.evidence_class_default == "targeting"


def test_winback_is_measured_default():
    play = PLAYS["winback_21_45"]
    assert play.evidence_class_default == "measured"
    assert play.measurement_metric == "reactivation_rate"


def test_aov_momentum_is_directional_only():
    # Memory.md: "AOV Momentum: directional only; do not forecast lift".
    play = PLAYS["aov_momentum"]
    assert play.evidence_class_default == "directional"


def test_onsite_funnel_watch_is_targeting():
    # T2.3: "Mark the latter as evidence_class_default='targeting' until
    # onsite data exists."
    play = PLAYS["onsite_funnel_watch"]
    assert play.evidence_class_default == "targeting"
    assert play.measurement_metric is None


def test_at_risk_repeat_buyer_rescue_is_targeting():
    # Memory.md: "remove assumed churn reduction" => targeting until a
    # measurement design is in place.
    play = PLAYS["at_risk_repeat_buyer_rescue"]
    assert play.evidence_class_default == "targeting"


def test_first_to_second_purchase_is_measurable():
    # Memory.md: "MVP-safe and preferred replacement for Journey Optimization."
    play = PLAYS["first_to_second_purchase"]
    assert play.evidence_class_default == "measured"
    assert play.measurement_metric is not None


def test_play_def_validation_rejects_targeting_with_metric():
    with pytest.raises(ValueError):
        PlayDef(
            play_id="bad",
            display_name="Bad",
            evidence_class_default="targeting",
            requires_inventory=False,
            audience_builder_ref="audience.bad",
            measurement_metric="something",  # invalid for targeting
            vertical_applicable=frozenset({"mixed"}),
            subvertical_applicable=None,
            prior_keys=[],
        )


def test_play_def_validation_rejects_bad_evidence_class():
    with pytest.raises(ValueError):
        PlayDef(
            play_id="bad",
            display_name="Bad",
            evidence_class_default="weak",  # internal-only, not allowed as default
            requires_inventory=False,
            audience_builder_ref="audience.bad",
            measurement_metric=None,
            vertical_applicable=frozenset({"mixed"}),
            subvertical_applicable=None,
            prior_keys=[],
        )


# ---------------------------------------------------------------------------
# Helpers.
# ---------------------------------------------------------------------------


def test_get_returns_none_for_unknown():
    assert get("definitely_not_a_play") is None


def test_get_returns_play_for_known_id():
    play = get("winback_21_45")
    assert play is not None
    assert play.play_id == "winback_21_45"


def test_all_play_ids_returns_keys_in_insertion_order():
    ids = all_play_ids()
    assert ids[0] == "winback_21_45"  # first inserted
    assert "onsite_funnel_watch" in ids


# ---------------------------------------------------------------------------
# Leaf-module guarantee: registry must NOT import action_engine.
# (Prevents an import cycle when M3 wires detection.)
# ---------------------------------------------------------------------------


def test_play_registry_does_not_import_action_engine():
    """Forbid any import of src.action_engine from the registry.

    Substring matching is too noisy (the docstring legitimately mentions
    'action_engine.py'); use line-level import-statement matching instead.
    """

    src = (REPO_ROOT / "src" / "play_registry.py").read_text(encoding="utf-8")
    bad_lines: list[str] = []
    for i, line in enumerate(src.splitlines(), start=1):
        stripped = line.lstrip()
        if stripped.startswith("import action_engine") or stripped.startswith("import src.action_engine"):
            bad_lines.append(f"line {i}: {line.rstrip()}")
        if stripped.startswith("from action_engine") or stripped.startswith("from src.action_engine"):
            bad_lines.append(f"line {i}: {line.rstrip()}")
        # also catch the dotted form within a single-line import
        if stripped.startswith("from .action_engine"):
            bad_lines.append(f"line {i}: {line.rstrip()}")
    assert not bad_lines, (
        "src/play_registry.py must remain leaf-level; it cannot import "
        "src.action_engine because M3+ will use the registry from the "
        "candidate detector. Offending imports:\n  " + "\n  ".join(bad_lines)
    )
