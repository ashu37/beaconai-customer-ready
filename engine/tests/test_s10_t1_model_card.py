"""S10-T1: ModelCard + ModelFitStatus contract tests.

Pins the closed four-value enum, the dataclass default shape, and the
round-trip contract through ``engine_run.to_dict``.
"""

from __future__ import annotations

import json

from src.engine_run import EngineRun
from src.predictive.model_card import ModelCard, ModelFitStatus


def test_model_fit_status_has_exactly_four_values():
    """Closed enum — exactly four values. New states require founder sign-off."""
    expected = {"VALIDATED", "PROVISIONAL", "INSUFFICIENT_DATA", "REFUSED"}
    assert {m.value for m in ModelFitStatus} == expected
    assert {m.name for m in ModelFitStatus} == expected


def test_model_fit_status_values_uppercase():
    """Vocabulary-stacking discipline: ModelFitStatus values are UPPERCASE
    to disambiguate from lowercase PriorValidationStatus (Option A)."""
    for status in ModelFitStatus:
        assert status.value == status.value.upper()


def test_model_card_default_shape():
    card = ModelCard()
    assert card.model_name == ""
    assert card.fit_status == ModelFitStatus.INSUFFICIENT_DATA
    assert card.fit_warnings == []
    assert card.parameters == {}
    assert card.training_window_days == 0
    assert card.n_observed == 0
    assert card.holdout_mape is None
    assert card.parquet_schema_version == 1


def test_model_card_docstring_mentions_prior_validation_parallel():
    """Vocabulary-stacking Option A: docstring explicitly states the
    parallel with PriorValidationStatus and the casing distinction."""
    from src.predictive import model_card as module
    doc = module.__doc__ or ""
    assert "PriorValidationStatus" in doc
    assert "Option A" in doc or "casing" in doc.lower()
    # PROVISIONAL semantics documented.
    assert "magnitudes" in doc.lower() or "magnitude" in doc.lower()
    # INSUFFICIENT_DATA vs REFUSED audit-story difference documented.
    assert "didn't try" in doc or "declined" in doc.lower()


def test_engine_run_predictive_models_default_empty_dict():
    """Flag-OFF / pre-S10 round-trip: predictive_models defaults to {}."""
    er = EngineRun()
    assert er.predictive_models == {}
    out = er.to_dict()
    assert "predictive_models" in out
    assert out["predictive_models"] == {}


def test_engine_run_predictive_models_round_trips():
    """ModelCard JSON shape round-trips through EngineRun.to_dict/from_dict."""
    er = EngineRun()
    card = ModelCard(
        model_name="bgnbd",
        fit_status=ModelFitStatus.VALIDATED,
        fit_warnings=[],
        parameters={"r": 0.5, "alpha": 8.0, "a": 0.2, "b": 2.1},
        training_window_days=180,
        n_observed=3844,
        holdout_mape=0.21,
        fit_timestamp="2026-05-26T00:00:00Z",
    )
    er.predictive_models["bgnbd"] = card
    out = er.to_dict()
    # Round-trip through json.
    payload = json.loads(json.dumps(out))
    er2 = EngineRun.from_dict(payload)
    assert "bgnbd" in er2.predictive_models
    bg = er2.predictive_models["bgnbd"]
    assert bg["fit_status"] == "VALIDATED"
    assert bg["n_observed"] == 3844
    assert bg["parquet_schema_version"] == 1


def test_engine_run_predictive_models_tolerates_missing_on_legacy_payload():
    """Pre-S10 payloads (no ``predictive_models`` key) round-trip with {}."""
    legacy = {
        "run_id": "r1",
        "store_id": "test_store",
        "schema_version": "1.0.0",
    }
    er = EngineRun.from_dict(legacy)
    assert er.predictive_models == {}
