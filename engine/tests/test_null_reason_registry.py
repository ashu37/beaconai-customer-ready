"""S13.6-T7.5 — NULL-REASON ENUM REGISTRY coverage test.

Pins the 3 shipped RULE A null-reason pairs from S13.6-T7a and documents
the deferred pairs (S13.7-T7b / KI-NEW-AA) as TODO markers.

Companion to the registry comment block in src/engine_run.py.
"""


def test_null_reason_enum_registry_coverage():
    """Every Optional field that has a paired _null_reason field on a contract
    dataclass in src/engine_run.py must have a corresponding null-reason enum
    declared in the same module.

    This test asserts the 3 shipped pairs are present and correctly typed.
    Deferred pairs (StoreProfile, ModelCard, CohortDiagnostics, CustomerIds)
    are noted as TODOs with KI references.
    """
    import dataclasses
    import inspect

    from src import engine_run

    # Find all dataclasses in engine_run
    dc_classes = [
        obj
        for name, obj in inspect.getmembers(engine_run, inspect.isclass)
        if dataclasses.is_dataclass(obj)
    ]

    # Collect all fields across all dataclasses
    all_fields: dict[str, set[str]] = {}
    for dc in dc_classes:
        field_names = {f.name for f in dataclasses.fields(dc)}
        all_fields[dc.__name__] = field_names

    # Assert the 2 top-level shipped pairs exist as (field, null_reason_field)
    # on their dataclasses, and that the corresponding enum is declared.
    # Pair 1: RevenueRange.suppression_reason  ← RevenueRangeSuppressionReason
    # Pair 2: EngineRun.month_2_delta_null_reason ← MonthDeltaNullReason
    shipped_pairs = [
        # (dataclass_name, optional_field, null_reason_field, enum_class_name)
        (
            "RevenueRange",
            "suppressed",
            "suppression_reason",
            "RevenueRangeSuppressionReason",
        ),
        (
            "EngineRun",
            "month_2_delta",
            "month_2_delta_null_reason",
            "MonthDeltaNullReason",
        ),
    ]

    for dc_name, field, null_field, enum_name in shipped_pairs:
        assert dc_name in all_fields, (
            f"Dataclass {dc_name} not found in engine_run"
        )
        assert null_field in all_fields[dc_name], (
            f"Expected {dc_name}.{null_field} to exist (paired with {field}) "
            f"per RULE A null-reason registry"
        )
        assert hasattr(engine_run, enum_name), (
            f"Expected enum {enum_name} to be declared in engine_run"
        )

    # Pair 3: PredictedSegment.segment_name_null_reason ← PredictedSegmentNullReason
    # PredictedSegment is an inner dataclass on PlayCard — check it separately.
    assert hasattr(engine_run, "PredictedSegment"), (
        "PredictedSegment not found in engine_run"
    )
    ps_fields = {f.name for f in dataclasses.fields(engine_run.PredictedSegment)}
    assert "segment_name_null_reason" in ps_fields, (
        "PredictedSegment.segment_name_null_reason missing — RULE A registry gap"
    )
    assert hasattr(engine_run, "PredictedSegmentNullReason"), (
        "PredictedSegmentNullReason enum missing from engine_run"
    )

    # Confirm the 3 shipped enum classes have the expected member counts
    # (guards against accidental member addition/removal at the seam).
    assert len(engine_run.RevenueRangeSuppressionReason) == 9, (
        "RevenueRangeSuppressionReason should have 9 members (T7a spec)"
    )
    assert len(engine_run.MonthDeltaNullReason) == 5, (
        "MonthDeltaNullReason should have 5 members (T7a spec)"
    )
    assert len(engine_run.PredictedSegmentNullReason) == 4, (
        "PredictedSegmentNullReason should have 4 members (T7a spec)"
    )

    # Confirm the 3 enums are exported in __all__ (DS R6 single-file authority).
    assert "RevenueRangeSuppressionReason" in engine_run.__all__, (
        "RevenueRangeSuppressionReason must be in engine_run.__all__"
    )
    assert "MonthDeltaNullReason" in engine_run.__all__, (
        "MonthDeltaNullReason must be in engine_run.__all__"
    )
    assert "PredictedSegmentNullReason" in engine_run.__all__, (
        "PredictedSegmentNullReason must be in engine_run.__all__"
    )

    # ---------------------------------------------------------------------------
    # S13.7-T1 SHIPPED: CustomerIdsNullReason declared in engine_run.py.
    # The PlayCard.audience.customer_ids field pairing is DEFERRED to
    # S13.7-T7b (Audience dataclass not extended; schema v2.0.0 frozen).
    # The enum itself is declared so the registry test does not fail-forward.
    # ---------------------------------------------------------------------------

    assert hasattr(engine_run, "CustomerIdsNullReason"), (
        "CustomerIdsNullReason must be declared in engine_run (shipped at S13.7-T1); "
        "PlayCard.audience.customer_ids field pairing deferred to S13.7-T7b"
    )
    assert len(engine_run.CustomerIdsNullReason) == 2, (
        "CustomerIdsNullReason should have 2 members: "
        "SUBSTRATE_REFUSED + AUDIENCE_RESOLVER_NOT_INVOKED (S13.7-T1 spec)"
    )
    assert "CustomerIdsNullReason" in engine_run.__all__, (
        "CustomerIdsNullReason must be in engine_run.__all__ (DS R6 single-file authority)"
    )

    # ---------------------------------------------------------------------------
    # S13.7-T7b SHIPPED: 3 deferred enums now declared (KI-NEW-AA closed).
    # ---------------------------------------------------------------------------

    # StoreProfileNullReason — paired with EngineRun.store_profile_null_reason
    assert hasattr(engine_run, "StoreProfileNullReason"), (
        "StoreProfileNullReason must be declared in engine_run (shipped at S13.7-T7b); "
        "closes KI-NEW-AA"
    )
    assert len(engine_run.StoreProfileNullReason) == 2, (
        "StoreProfileNullReason should have 2 members: "
        "PROFILE_NOT_LOADED + ONBOARDING_INCOMPLETE (S13.7-T7b spec)"
    )
    assert "StoreProfileNullReason" in engine_run.__all__, (
        "StoreProfileNullReason must be in engine_run.__all__ (DS R6 single-file authority)"
    )

    # ModelCardAbsenceReason — dict field; enum declared for agent reference only
    assert hasattr(engine_run, "ModelCardAbsenceReason"), (
        "ModelCardAbsenceReason must be declared in engine_run (shipped at S13.7-T7b); "
        "dict field — no paired _null_reason field"
    )
    assert len(engine_run.ModelCardAbsenceReason) == 3, (
        "ModelCardAbsenceReason should have 3 members: "
        "SUBSTRATE_NOT_RUN + SUBSTRATE_REFUSED + INSUFFICIENT_DATA (S13.7-T7b spec)"
    )
    assert "ModelCardAbsenceReason" in engine_run.__all__, (
        "ModelCardAbsenceReason must be in engine_run.__all__ (DS R6 single-file authority)"
    )

    # CohortDiagnosticsAbsenceReason — dict field; enum declared for agent reference only
    assert hasattr(engine_run, "CohortDiagnosticsAbsenceReason"), (
        "CohortDiagnosticsAbsenceReason must be declared in engine_run (shipped at S13.7-T7b); "
        "dict field — no paired _null_reason field"
    )
    assert len(engine_run.CohortDiagnosticsAbsenceReason) == 2, (
        "CohortDiagnosticsAbsenceReason should have 2 members: "
        "INSUFFICIENT_COHORT_DEPTH + SUBSTRATE_REFUSED (S13.7-T7b spec)"
    )
    assert "CohortDiagnosticsAbsenceReason" in engine_run.__all__, (
        "CohortDiagnosticsAbsenceReason must be in engine_run.__all__ "
        "(DS R6 single-file authority)"
    )

    # Assert EngineRun.store_profile_null_reason field exists (paired field)
    import dataclasses
    er_fields = {f.name for f in dataclasses.fields(engine_run.EngineRun)}
    assert "store_profile_null_reason" in er_fields, (
        "EngineRun.store_profile_null_reason must exist (paired with store_profile "
        "per RULE A — S13.7-T7b / KI-NEW-AA)"
    )
