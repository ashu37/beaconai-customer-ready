"""DS Architect QA Required Change 5 — calibration stub shape.

The stub MUST return EXACTLY three keys, each mapping to an empty dict
in Phase 1. The shape is the contract a future calibration layer plugs
into; widening or renaming requires a coordinated change.
"""

from __future__ import annotations

from src.calibration_stub import load_realization_factors


REQUIRED_KEYS = {"prior_overrides", "evidence_thresholds", "materiality_overrides"}


def test_load_realization_factors_returns_exact_three_keys():
    out = load_realization_factors()
    assert isinstance(out, dict)
    assert set(out.keys()) == REQUIRED_KEYS


def test_load_realization_factors_all_values_are_empty_dicts():
    out = load_realization_factors()
    for k in REQUIRED_KEYS:
        assert isinstance(out[k], dict), f"{k!r} should be a dict"
        assert out[k] == {}, f"{k!r} should be empty in Phase 1"


def test_load_realization_factors_accepts_any_history_path_argument():
    # The stub does not read the file in Phase 1; the argument is the
    # future-shape anchor only. Arbitrary inputs must not raise.
    for path in (None, "", "/nonexistent/path", 42, ["weird", "list"]):
        out = load_realization_factors(path)
        assert set(out.keys()) == REQUIRED_KEYS


def test_load_realization_factors_returns_fresh_dict_each_call():
    a = load_realization_factors()
    b = load_realization_factors()
    a["prior_overrides"]["mutated"] = "x"
    # Mutation of one return value MUST NOT affect the next call.
    assert "mutated" not in b["prior_overrides"]


def test_load_realization_factors_no_extra_keys():
    out = load_realization_factors()
    extra = set(out.keys()) - REQUIRED_KEYS
    assert not extra, f"unexpected extra keys: {extra}"
