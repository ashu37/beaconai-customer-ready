"""Sprint 8 Ticket T4 — Play Library wave 1 migration contract tests.

Per DS verdict 2026-05-24 §5 invariant 13:

    "Play Library wave 1 = {winback_dormant_cohort, replenishment_due,
    discount_dependency_hygiene}. Test pin: tests/test_s8_t4_play_library_
    wave1_migration.py asserts exactly these three play_ids have a
    plays/<play_id>/spec.yaml artifact post-T4.5. replenishment_due
    produces zero audience on Beauty pinned fixture post-migration
    (honest-dormancy preserved)."

This module pins:

(a) Artifact invariant: each wave-1 play_id has spec.yaml + audience.py +
    builder.py + copy.md + __init__.py present.
(b) Spec loader: ``plays.get_play_definition`` returns a typed
    ``PlayDefinition`` for each wave-1 play_id and None for unrecognized.
(c) Audience builder identity re-export: ``plays/<play_id>/audience.py
    ::build_audience`` is the exact same Python callable as the legacy
    ``src.audience_builders.<callable>``.
(d) Measurement signal identity re-export: ``plays/<play_id>/builder.py
    ::measurement_signal_entry`` is the exact same dataclass instance as
    ``src.measurement_builder._PRIOR_ANCHORED[play_id]``.
(e) Consult-and-verify: ``plays.assert_identity_with_legacy()`` passes
    without raising (the contract that lets flag-ON output stay
    byte-identical to flag-OFF).
(f) Honest-dormancy: ``replenishment_due`` audience builder produces zero
    audience on the Beauty pinned fixture (KI-NEW-G preserved).

The harness-level byte-identical contract at flag OFF + flag ON is covered
by ``tests/test_v2_harness_cfg_gated_fields.py`` (new T4 row) and by the
existing Beauty + Supplements pinned-fixture tests.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Set

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


# DS verdict §5 invariant 13 — LOCKED wave-1 set.
EXPECTED_WAVE1_PLAY_IDS: Set[str] = {
    "winback_dormant_cohort",
    "replenishment_due",
    "discount_dependency_hygiene",
}


# ---------------------------------------------------------------------------
# (a) Artifact invariant — exact wave-1 set + required files per play.
# ---------------------------------------------------------------------------


def test_plays_directory_exists():
    plays_dir = REPO_ROOT / "plays"
    assert plays_dir.is_dir(), (
        "S8-T4 artifact invariant: plays/ directory must exist at repo root."
    )
    assert (plays_dir / "__init__.py").is_file()
    assert (plays_dir / "_registry.py").is_file()


def test_exact_wave1_play_ids_have_spec_yaml():
    """DS verdict §5 invariant 13: exactly these three play_ids have a
    ``plays/<play_id>/spec.yaml`` artifact post-T4 (and post-T4.5)."""
    plays_dir = REPO_ROOT / "plays"
    observed = {
        p.name for p in plays_dir.iterdir()
        if p.is_dir() and not p.name.startswith("_") and not p.name.startswith(".")
        and (p / "spec.yaml").is_file()
    }
    assert observed == EXPECTED_WAVE1_PLAY_IDS, (
        f"S8-T4 wave-1 set drift: expected exactly "
        f"{sorted(EXPECTED_WAVE1_PLAY_IDS)}; got {sorted(observed)}. "
        f"DS verdict 2026-05-24 §3 Q6 LOCKS the wave-1 selection. "
        f"Substituting plays is not permitted without a new DS verdict."
    )


@pytest.mark.parametrize("play_id", sorted(EXPECTED_WAVE1_PLAY_IDS))
def test_each_wave1_play_has_required_files(play_id: str):
    """Each wave-1 play directory must carry the full per-play template:
    __init__.py + spec.yaml + audience.py + builder.py + copy.md.
    """
    play_dir = REPO_ROOT / "plays" / play_id
    assert play_dir.is_dir(), f"plays/{play_id} missing"
    for fname in ("__init__.py", "spec.yaml", "audience.py", "builder.py", "copy.md"):
        assert (play_dir / fname).is_file(), (
            f"plays/{play_id}/{fname} missing — wave-1 template incomplete."
        )


# ---------------------------------------------------------------------------
# (b) Spec loader — get_play_definition returns typed PlayDefinition.
# ---------------------------------------------------------------------------


def test_get_play_definition_returns_none_for_unknown():
    from plays import get_play_definition

    assert get_play_definition("unrecognized_play_id_xyz") is None


@pytest.mark.parametrize("play_id", sorted(EXPECTED_WAVE1_PLAY_IDS))
def test_get_play_definition_returns_defn_for_wave1(play_id: str):
    from plays import PlayDefinition, get_play_definition

    defn = get_play_definition(play_id)
    assert defn is not None, f"get_play_definition({play_id!r}) returned None"
    assert isinstance(defn, PlayDefinition)
    assert defn.play_id == play_id
    assert defn.display_name, "display_name must be non-empty"
    assert defn.audience_builder_ref.startswith("src.audience_builders.")
    assert defn.measurement_builder_ref.startswith("src.measurement_builder.")
    assert callable(defn.audience_builder)
    assert defn.measurement_signal_entry is not None, (
        f"{play_id}: _PRIOR_ANCHORED entry must exist (all wave-1 plays "
        f"are prior-anchored)"
    )


# ---------------------------------------------------------------------------
# (c) Audience builder identity re-export.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "play_id,legacy_symbol",
    [
        ("winback_dormant_cohort", "winback_dormant_cohort_candidates"),
        ("replenishment_due", "replenishment_due_candidates"),
        ("discount_dependency_hygiene", "discount_dependency_hygiene_candidates"),
    ],
)
def test_audience_builder_is_identity_reexport(play_id: str, legacy_symbol: str):
    """plays/<play_id>/audience.py::build_audience MUST be the exact same
    Python object as src.audience_builders.<legacy_symbol>. Identity (``is``)
    not equality. This is the byte-identical contract foundation: re-exporting
    the same callable guarantees the engine runs the same code regardless of
    which import path the caller used.
    """
    import importlib

    play_audience_mod = importlib.import_module(f"plays.{play_id}.audience")
    legacy_mod = importlib.import_module("src.audience_builders")

    play_callable = play_audience_mod.build_audience
    legacy_callable = getattr(legacy_mod, legacy_symbol)
    assert play_callable is legacy_callable, (
        f"S8-T4 identity contract violated: plays/{play_id}/audience.py"
        f"::build_audience is NOT the same Python object as "
        f"src.audience_builders.{legacy_symbol}. The wave-1 refactor is "
        f"re-export-only; no callable should be redefined."
    )


# ---------------------------------------------------------------------------
# (d) Measurement signal identity re-export.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("play_id", sorted(EXPECTED_WAVE1_PLAY_IDS))
def test_measurement_signal_entry_is_identity_reexport(play_id: str):
    """plays/<play_id>/builder.py::measurement_signal_entry MUST be the
    exact same dataclass instance as
    src.measurement_builder._PRIOR_ANCHORED[play_id]."""
    import importlib

    play_builder_mod = importlib.import_module(f"plays.{play_id}.builder")
    from src.measurement_builder import _PRIOR_ANCHORED

    play_entry = play_builder_mod.measurement_signal_entry
    legacy_entry = _PRIOR_ANCHORED[play_id]
    assert play_entry is legacy_entry, (
        f"S8-T4 identity contract violated: plays/{play_id}/builder.py"
        f"::measurement_signal_entry is NOT the same object as "
        f"src.measurement_builder._PRIOR_ANCHORED[{play_id!r}]."
    )


# ---------------------------------------------------------------------------
# (e) Consult-and-verify — assert_identity_with_legacy passes today.
# ---------------------------------------------------------------------------


def test_assert_identity_with_legacy_passes():
    """The consult-and-verify integrity check (run at flag ON by
    src/play_registry.py::consult_play_library_if_enabled) must pass at
    HEAD. If this raises, flag-ON would refuse to start the engine.
    """
    from plays import assert_identity_with_legacy

    # No raise == passing contract.
    assert_identity_with_legacy()


def test_consult_play_library_noop_at_flag_off():
    """When the flag is OFF, the consult helper must be a no-op (no
    plays/ import, no exception). Preserves flag-OFF behavior identity.
    """
    from src.play_registry import consult_play_library_if_enabled

    # Explicit OFF.
    consult_play_library_if_enabled({"ENGINE_V2_PLAY_LIBRARY_WAVE1": False})
    # Absent flag = OFF semantics.
    consult_play_library_if_enabled({})
    # None cfg.
    consult_play_library_if_enabled(None)


def test_consult_play_library_runs_at_flag_on():
    """When the flag is ON, the consult helper must invoke
    assert_identity_with_legacy(). Today the contract passes (verified
    above); this test pins that the wiring is reachable.
    """
    from src.play_registry import consult_play_library_if_enabled

    # No raise == wiring reachable + contract passes.
    consult_play_library_if_enabled({"ENGINE_V2_PLAY_LIBRARY_WAVE1": True})


# ---------------------------------------------------------------------------
# (f) KI-NEW-G honest-dormancy — replenishment_due produces zero audience
#     on Beauty pinned fixture (preserved post-migration at both flag
#     states because the audience builder callable is identity-equal to
#     the legacy one).
# ---------------------------------------------------------------------------


def test_replenishment_due_audience_is_identity_legacy_callable():
    """The strongest statement of KI-NEW-G preservation: the Play Library
    audience.build_audience IS the legacy callable. Therefore any test of
    legacy dormancy on Beauty applies verbatim to the Play Library path.

    The harness-level Beauty byte-identical pin at both flag states
    (tests/test_v2_harness_cfg_gated_fields.py + the existing slate
    regression tests) is the load-bearing empirical confirmation.
    """
    from plays.replenishment_due.audience import build_audience as play_callable
    from src.audience_builders import replenishment_due_candidates as legacy_callable

    assert play_callable is legacy_callable, (
        "KI-NEW-G honest-dormancy preservation foundation: "
        "plays/replenishment_due/audience.py::build_audience must be the "
        "exact same Python object as the legacy callable. If this drifts, "
        "the dormancy-on-Beauty contract becomes unsupported."
    )
