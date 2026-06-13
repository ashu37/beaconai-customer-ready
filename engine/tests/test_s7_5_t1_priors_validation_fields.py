"""Sprint 7.5 Ticket T1 — PriorEntry validation_status / source_artifact / effective_n.

Pins the closed-enum contract + additive-default behavior introduced by
S7.5-T1. Every existing entry in ``config/priors.yaml`` must continue to
parse without modification (default ``HEURISTIC_UNVALIDATED``); new
entries that author the field round-trip; unknown enum strings raise.

See ``agent_outputs/implementation-manager-s7_5-priors-validation-plan.md``
S7.5-T1 spec and ``ARCHITECTURE_PLAN.md`` Part III-1 §III-1 Step 1 for
the design rationale.
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
from src.priors_loader import (
    PriorEntry,
    PriorValidationStatus,
    PriorsValidationError,
)


@pytest.fixture(autouse=True)
def _reset_cache():
    PL.clear_cache()
    yield
    PL.clear_cache()


# ---------------------------------------------------------------------------
# Closed-enum contract: exactly 5 values, exact spelling.
# ---------------------------------------------------------------------------


def test_validation_status_enum_has_exactly_five_members():
    members = {m.value for m in PriorValidationStatus}
    assert members == {
        "validated_external",
        "validated_internal",
        "elicited_expert",
        "heuristic_unvalidated",
        "placeholder",
    }


def test_validation_status_enum_member_names_pinned():
    assert PriorValidationStatus.VALIDATED_EXTERNAL.value == "validated_external"
    assert PriorValidationStatus.VALIDATED_INTERNAL.value == "validated_internal"
    assert PriorValidationStatus.ELICITED_EXPERT.value == "elicited_expert"
    assert PriorValidationStatus.HEURISTIC_UNVALIDATED.value == "heuristic_unvalidated"
    assert PriorValidationStatus.PLACEHOLDER.value == "placeholder"


# ---------------------------------------------------------------------------
# PriorEntry dataclass shape.
# ---------------------------------------------------------------------------


def test_prior_entry_has_three_new_fields_with_safe_defaults():
    e = PriorEntry(
        name="base_rate",
        value=0.1,
        range_p10=0.05,
        range_p90=0.2,
        source_class="observational",
    )
    assert e.validation_status is PriorValidationStatus.HEURISTIC_UNVALIDATED
    assert e.source_artifact is None
    assert e.effective_n is None


def test_prior_entry_accepts_explicit_validation_fields():
    e = PriorEntry(
        name="base_rate",
        value=0.1,
        range_p10=0.05,
        range_p90=0.2,
        source_class="observational",
        validation_status=PriorValidationStatus.VALIDATED_EXTERNAL,
        source_artifact="config/priors_sources/winback_21_45__base_rate__beauty.md",
        effective_n=1200,
    )
    assert e.validation_status is PriorValidationStatus.VALIDATED_EXTERNAL
    assert e.source_artifact == "config/priors_sources/winback_21_45__base_rate__beauty.md"
    assert e.effective_n == 1200


# ---------------------------------------------------------------------------
# YAML loader: backwards-compat — every existing entry parses with defaults.
# ---------------------------------------------------------------------------


def test_real_priors_yaml_loads_without_raising():
    """The shipped ``config/priors.yaml`` (zero T1 fields authored) parses cleanly."""
    doc = PL.load_priors()
    assert isinstance(doc, dict)
    assert "plays" in doc


def test_real_priors_yaml_every_entry_resolves_to_a_closed_enum_value():
    """Post-T1.5, every entry in ``config/priors.yaml`` authors
    ``validation_status`` explicitly. This test asserts the loader returns
    a closed-enum member for every entry (no AttributeError, no string
    leakage). The per-status distribution is pinned by
    ``test_s7_5_t1_5_priors_audit.py``; T1's test only enforces the
    closed-enum invariant.
    """
    doc = PL.load_priors()
    plays = doc.get("plays", {})
    assert plays, "config/priors.yaml has no plays"

    seen_any = False
    for play_id in plays:
        rows = PL.list_priors_for_play(play_id)
        for row in rows:
            entry = PL.get_prior(
                play_id,
                key=row["name"],
                vertical=(row.get("applies_to") or {}).get("vertical"),
                subvertical=(row.get("applies_to") or {}).get("subvertical"),
            )
            if entry is None:
                continue
            seen_any = True
            assert isinstance(
                entry.validation_status, PriorValidationStatus
            ), f"{play_id}.{row['name']} not a closed-enum value"
            # Post-T2: validated_external entries author source_artifact +
            # effective_n; non-validated entries leave both null. This
            # T1-level test asserts the closed-enum invariant only; the
            # detailed shape of validated entries is pinned by
            # tests/test_s7_5_t2_external_priors.py.
            if entry.validation_status is PriorValidationStatus.HEURISTIC_UNVALIDATED:
                assert entry.source_artifact is None
                assert entry.effective_n is None
    assert seen_any, "no priors resolved from real YAML — fixture drift"


# ---------------------------------------------------------------------------
# YAML loader: T1 fields authored explicitly round-trip.
# ---------------------------------------------------------------------------


def _write_yaml(tmp_path: Path, body: str) -> Path:
    p = tmp_path / "priors.yaml"
    p.write_text(body, encoding="utf-8")
    return p


def test_loader_parses_authored_validation_status_fields(tmp_path: Path):
    body = """
schema_version: "1.0.0"
plays:
  test_play:
    - name: base_rate
      value: 0.10
      range_p10: 0.05
      range_p90: 0.20
      source_class: observational
      validation_status: validated_external
      source_artifact: config/priors_sources/test_play__base_rate.md
      effective_n: 1500
      applies_to: { vertical: beauty }
"""
    path = _write_yaml(tmp_path, body)
    PL.clear_cache()
    entry = PL.get_prior("test_play", key="base_rate", vertical="beauty", path=path)
    assert entry is not None
    assert entry.validation_status is PriorValidationStatus.VALIDATED_EXTERNAL
    assert entry.source_artifact == "config/priors_sources/test_play__base_rate.md"
    assert entry.effective_n == 1500


def test_loader_parses_placeholder_status(tmp_path: Path):
    body = """
schema_version: "1.0.0"
plays:
  test_play:
    - name: second_purchase_lift
      value: 0.0
      range_p10: 0.0
      range_p90: 0.0
      source_class: expert
      validation_status: placeholder
      applies_to: { vertical: "*" }
"""
    path = _write_yaml(tmp_path, body)
    PL.clear_cache()
    entry = PL.get_prior("test_play", key="second_purchase_lift", path=path)
    assert entry is not None
    assert entry.validation_status is PriorValidationStatus.PLACEHOLDER


def test_loader_defaults_missing_field_to_heuristic_unvalidated(tmp_path: Path):
    body = """
schema_version: "1.0.0"
plays:
  test_play:
    - name: base_rate
      value: 0.10
      range_p10: 0.05
      range_p90: 0.20
      source_class: observational
      applies_to: { vertical: beauty }
"""
    path = _write_yaml(tmp_path, body)
    PL.clear_cache()
    entry = PL.get_prior("test_play", key="base_rate", vertical="beauty", path=path)
    assert entry is not None
    assert entry.validation_status is PriorValidationStatus.HEURISTIC_UNVALIDATED


# ---------------------------------------------------------------------------
# Closed-enum contract: unknown strings raise a clear error.
# ---------------------------------------------------------------------------


def test_loader_rejects_unknown_validation_status_string(tmp_path: Path):
    body = """
schema_version: "1.0.0"
plays:
  test_play:
    - name: base_rate
      value: 0.10
      range_p10: 0.05
      range_p90: 0.20
      source_class: observational
      validation_status: totally_made_up_value
      applies_to: { vertical: beauty }
"""
    path = _write_yaml(tmp_path, body)
    PL.clear_cache()
    with pytest.raises(PriorsValidationError) as excinfo:
        PL.get_prior("test_play", key="base_rate", vertical="beauty", path=path)
    msg = str(excinfo.value)
    assert "totally_made_up_value" in msg
    assert "test_play" in msg
    assert "base_rate" in msg
    # All five legal values should be enumerated in the error.
    for v in (
        "validated_external",
        "validated_internal",
        "elicited_expert",
        "heuristic_unvalidated",
        "placeholder",
    ):
        assert v in msg


def test_priors_validation_error_is_value_error_subclass():
    """Upstream callers using broad ``ValueError`` catches still trip."""
    assert issubclass(PriorsValidationError, ValueError)


# ---------------------------------------------------------------------------
# effective_n / source_artifact tolerant-coercion edge cases.
# ---------------------------------------------------------------------------


def test_loader_tolerates_whitespace_only_source_artifact(tmp_path: Path):
    body = """
schema_version: "1.0.0"
plays:
  test_play:
    - name: base_rate
      value: 0.10
      range_p10: 0.05
      range_p90: 0.20
      source_class: observational
      source_artifact: "   "
      applies_to: { vertical: beauty }
"""
    path = _write_yaml(tmp_path, body)
    PL.clear_cache()
    entry = PL.get_prior("test_play", key="base_rate", vertical="beauty", path=path)
    assert entry is not None
    assert entry.source_artifact is None


def test_loader_tolerates_non_positive_effective_n(tmp_path: Path):
    body = """
schema_version: "1.0.0"
plays:
  test_play:
    - name: base_rate
      value: 0.10
      range_p10: 0.05
      range_p90: 0.20
      source_class: observational
      effective_n: 0
      applies_to: { vertical: beauty }
"""
    path = _write_yaml(tmp_path, body)
    PL.clear_cache()
    entry = PL.get_prior("test_play", key="base_rate", vertical="beauty", path=path)
    assert entry is not None
    assert entry.effective_n is None


def test_loader_tolerates_non_numeric_effective_n(tmp_path: Path):
    body = """
schema_version: "1.0.0"
plays:
  test_play:
    - name: base_rate
      value: 0.10
      range_p10: 0.05
      range_p90: 0.20
      source_class: observational
      effective_n: "not-a-number"
      applies_to: { vertical: beauty }
"""
    path = _write_yaml(tmp_path, body)
    PL.clear_cache()
    entry = PL.get_prior("test_play", key="base_rate", vertical="beauty", path=path)
    assert entry is not None
    assert entry.effective_n is None


# ---------------------------------------------------------------------------
# Module surface: __all__ exports the new symbols.
# ---------------------------------------------------------------------------


def test_module_exports_new_symbols():
    assert "PriorValidationStatus" in PL.__all__
    assert "PriorsValidationError" in PL.__all__
