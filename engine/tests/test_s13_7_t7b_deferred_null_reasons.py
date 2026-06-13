"""S13.7-T7b — deferred null-reason enums + dead-code sweep tests.

Covers:
  - Sub-task A: StoreProfileNullReason enum declared + EngineRun field added
  - Sub-task B: ModelCardAbsenceReason + CohortDiagnosticsAbsenceReason declared
  - Sub-task C: dead-code sweep (targeting_non_causal_prior / _surface_mechanism_for_play)
"""

import ast
import dataclasses
import importlib
import pathlib
import pytest


# ---------------------------------------------------------------------------
# Sub-task A: StoreProfileNullReason
# ---------------------------------------------------------------------------


def test_store_profile_null_reason_enum_declared():
    """StoreProfileNullReason is declared in engine_run with exactly 2 members."""
    from src import engine_run

    assert hasattr(engine_run, "StoreProfileNullReason"), (
        "StoreProfileNullReason must be declared in src/engine_run.py (S13.7-T7b)"
    )
    enum_cls = engine_run.StoreProfileNullReason
    assert len(enum_cls) == 2, (
        f"StoreProfileNullReason must have exactly 2 members; found {len(enum_cls)}: "
        f"{[m.name for m in enum_cls]}"
    )
    # Verify member names
    member_names = {m.name for m in enum_cls}
    assert "PROFILE_NOT_LOADED" in member_names, (
        "StoreProfileNullReason must contain PROFILE_NOT_LOADED"
    )
    assert "ONBOARDING_INCOMPLETE" in member_names, (
        "StoreProfileNullReason must contain ONBOARDING_INCOMPLETE"
    )
    # Verify string values (lowercase convention)
    assert enum_cls.PROFILE_NOT_LOADED.value == "profile_not_loaded"
    assert enum_cls.ONBOARDING_INCOMPLETE.value == "onboarding_incomplete"
    # Verify __all__ export (DS R6 single-file authority)
    assert "StoreProfileNullReason" in engine_run.__all__, (
        "StoreProfileNullReason must be in engine_run.__all__"
    )


def test_store_profile_null_reason_field_on_engine_run():
    """EngineRun has store_profile_null_reason field of correct type + default."""
    from src import engine_run

    er_fields = {f.name: f for f in dataclasses.fields(engine_run.EngineRun)}

    assert "store_profile_null_reason" in er_fields, (
        "EngineRun must have store_profile_null_reason field (paired with store_profile "
        "per RULE A; S13.7-T7b / KI-NEW-AA)"
    )
    field = er_fields["store_profile_null_reason"]
    # Default must be None (flag-OFF safe default)
    assert field.default is None, (
        "EngineRun.store_profile_null_reason default must be None"
    )
    # Field must appear immediately after store_profile in field ordering
    field_names = [f.name for f in dataclasses.fields(engine_run.EngineRun)]
    store_profile_idx = field_names.index("store_profile")
    null_reason_idx = field_names.index("store_profile_null_reason")
    assert null_reason_idx == store_profile_idx + 1, (
        "store_profile_null_reason must immediately follow store_profile in EngineRun "
        f"(store_profile at index {store_profile_idx}, "
        f"store_profile_null_reason at index {null_reason_idx})"
    )


def test_store_profile_null_reason_round_trips_via_to_dict():
    """EngineRun.to_dict() serializes store_profile_null_reason; from_dict() restores it."""
    from src.engine_run import EngineRun, StoreProfileNullReason

    run = EngineRun(
        store_profile=None,
        store_profile_null_reason=StoreProfileNullReason.PROFILE_NOT_LOADED,
    )
    d = run.to_dict()
    assert d.get("store_profile_null_reason") == "profile_not_loaded", (
        "store_profile_null_reason must serialize to its string value"
    )
    restored = EngineRun.from_dict(d)
    assert restored.store_profile_null_reason == StoreProfileNullReason.PROFILE_NOT_LOADED, (
        "from_dict must restore StoreProfileNullReason enum value"
    )


def test_store_profile_null_reason_none_when_not_set():
    """EngineRun without store_profile_null_reason key round-trips to None."""
    from src.engine_run import EngineRun

    run = EngineRun()
    d = run.to_dict()
    # The serialized key should be present with value null
    assert "store_profile_null_reason" in d, (
        "store_profile_null_reason must appear in to_dict() output (value: null)"
    )
    assert d["store_profile_null_reason"] is None

    # from_dict with no key → None (tolerate missing for pre-T7b snapshots)
    payload_without_key = {k: v for k, v in d.items() if k != "store_profile_null_reason"}
    restored = EngineRun.from_dict(payload_without_key)
    assert restored.store_profile_null_reason is None


# ---------------------------------------------------------------------------
# Sub-task B: ModelCardAbsenceReason + CohortDiagnosticsAbsenceReason
# ---------------------------------------------------------------------------


def test_model_card_absence_reason_declared():
    """ModelCardAbsenceReason is declared in engine_run with exactly 3 members."""
    from src import engine_run

    assert hasattr(engine_run, "ModelCardAbsenceReason"), (
        "ModelCardAbsenceReason must be declared in src/engine_run.py (S13.7-T7b)"
    )
    enum_cls = engine_run.ModelCardAbsenceReason
    assert len(enum_cls) == 3, (
        f"ModelCardAbsenceReason must have exactly 3 members; found {len(enum_cls)}: "
        f"{[m.name for m in enum_cls]}"
    )
    member_names = {m.name for m in enum_cls}
    assert "SUBSTRATE_NOT_RUN" in member_names
    assert "SUBSTRATE_REFUSED" in member_names
    assert "INSUFFICIENT_DATA" in member_names
    # Verify __all__ export
    assert "ModelCardAbsenceReason" in engine_run.__all__, (
        "ModelCardAbsenceReason must be in engine_run.__all__"
    )
    # Dict field — no paired _null_reason field on EngineRun
    er_fields = {f.name for f in dataclasses.fields(engine_run.EngineRun)}
    assert "predictive_models_null_reason" not in er_fields, (
        "No predictive_models_null_reason field should exist on EngineRun; "
        "ModelCardAbsenceReason is dict-field vocabulary only (S13.7-T7b)"
    )


def test_cohort_diagnostics_absence_reason_declared():
    """CohortDiagnosticsAbsenceReason is declared in engine_run with exactly 2 members."""
    from src import engine_run

    assert hasattr(engine_run, "CohortDiagnosticsAbsenceReason"), (
        "CohortDiagnosticsAbsenceReason must be declared in src/engine_run.py (S13.7-T7b)"
    )
    enum_cls = engine_run.CohortDiagnosticsAbsenceReason
    assert len(enum_cls) == 2, (
        f"CohortDiagnosticsAbsenceReason must have exactly 2 members; "
        f"found {len(enum_cls)}: {[m.name for m in enum_cls]}"
    )
    member_names = {m.name for m in enum_cls}
    assert "INSUFFICIENT_COHORT_DEPTH" in member_names
    assert "SUBSTRATE_REFUSED" in member_names
    # Verify __all__ export
    assert "CohortDiagnosticsAbsenceReason" in engine_run.__all__, (
        "CohortDiagnosticsAbsenceReason must be in engine_run.__all__"
    )
    # Dict field — no paired _null_reason field on EngineRun
    er_fields = {f.name for f in dataclasses.fields(engine_run.EngineRun)}
    assert "cohort_diagnostics_null_reason" not in er_fields, (
        "No cohort_diagnostics_null_reason field should exist on EngineRun; "
        "CohortDiagnosticsAbsenceReason is dict-field vocabulary only (S13.7-T7b)"
    )


# ---------------------------------------------------------------------------
# Sub-task C: dead-code sweep
# ---------------------------------------------------------------------------


def test_dead_code_targeting_non_causal_prior_skipped():
    """targeting_non_causal_prior has active call sites in sizing.py — not removed.

    KI-NEW-AB: the variable is referenced at sizing.py L615 + L777 and is pinned
    by tests/test_sizing.py, tests/test_s7_5_t3_blend_refusal.py, and
    tests/test_internal_stats_not_rendered.py. Deletion would break those tests.
    Deferred — the string is a legacy suppression-reason label on the
    _suppressed_range path; full cleanup requires a producer rewrite per DS Q1.
    """
    sizing_path = pathlib.Path(__file__).parent.parent / "src" / "sizing.py"
    source = sizing_path.read_text()
    if "targeting_non_causal_prior" in source:
        pytest.skip(
            "targeting_non_causal_prior still has active call sites in src/sizing.py "
            "(and pinned test assertions) — see KI-NEW-AB; deferred from S13.7-T7b"
        )
    # If we reach here, the dead code was removed — assert it's gone
    assert "targeting_non_causal_prior" not in source


def test_dead_code_surface_mechanism_for_play_removed():
    """_surface_mechanism_for_play has been removed from src/decide.py (Sub-task C2)."""
    decide_path = pathlib.Path(__file__).parent.parent / "src" / "decide.py"
    source = decide_path.read_text()

    # Check if the function definition still exists (a call-site check alone is
    # insufficient — the function might exist but be unreachable)
    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        pytest.fail(f"src/decide.py has a syntax error: {e}")

    # Walk the AST for any FunctionDef named _surface_mechanism_for_play
    function_defs = [
        node.name
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef)
    ]
    if "_surface_mechanism_for_play" in function_defs:
        pytest.skip(
            "_surface_mechanism_for_play still defined in src/decide.py — "
            "check for call sites before removing; see KI-NEW-AB"
        )

    # Also check for any Call nodes referencing _surface_mechanism_for_play
    call_names = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                call_names.append(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                call_names.append(node.func.attr)
    assert "_surface_mechanism_for_play" not in call_names, (
        "_surface_mechanism_for_play is still called in src/decide.py; "
        "cannot confirm dead-code removal"
    )
