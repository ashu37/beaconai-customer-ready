"""S13.7-T2 — JSON Schema generator tests.

Two required tests per ticket spec:
1. test_schema_file_exists_after_generation
2. test_schema_engine_run_has_required_fields

Plus additional structural checks:
- EngineRun is in $defs.
- $defs includes all key enums and dataclasses.
- Dry-run produces valid JSON.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_GENERATOR = _REPO_ROOT / "tools" / "generate_schema.py"


def _run_generator_dry_run() -> str:
    """Run generate_schema.py --dry-run and return captured stdout."""
    result = subprocess.run(
        [sys.executable, str(_GENERATOR), "--dry-run"],
        capture_output=True,
        text=True,
        cwd=str(_REPO_ROOT),
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"generate_schema.py --dry-run failed (exit {result.returncode}):\n"
            f"stdout: {result.stdout}\n"
            f"stderr: {result.stderr}"
        )
    return result.stdout


# ---------------------------------------------------------------------------
# Test 1: dry-run output is valid JSON and contains required top-level keys
# ---------------------------------------------------------------------------


def test_schema_file_exists_after_generation():
    """--dry-run produces valid JSON containing $schema, title, $defs, and EngineRun in $defs."""
    stdout = _run_generator_dry_run()

    # Must be valid JSON.
    try:
        schema = json.loads(stdout)
    except json.JSONDecodeError as e:
        raise AssertionError(
            f"generate_schema.py --dry-run produced invalid JSON: {e}\n"
            f"First 200 chars: {stdout[:200]!r}"
        )

    # Must contain "$schema".
    assert "$schema" in schema, (
        f"Schema missing '$schema' key. Top-level keys: {list(schema.keys())}"
    )
    assert "json-schema.org" in schema["$schema"], (
        f"$schema value does not look like a JSON Schema URI: {schema['$schema']!r}"
    )

    # Must contain "title".
    assert "title" in schema, (
        f"Schema missing 'title' key. Top-level keys: {list(schema.keys())}"
    )

    # Must contain "$defs".
    assert "$defs" in schema, (
        f"Schema missing '$defs' key. Top-level keys: {list(schema.keys())}"
    )

    # Must contain "EngineRun" in $defs.
    defs = schema["$defs"]
    assert "EngineRun" in defs, (
        f"'EngineRun' not found in $defs. Keys: {list(defs.keys())[:20]}"
    )


# ---------------------------------------------------------------------------
# Test 2: EngineRun $defs entry has properties and required lists
# ---------------------------------------------------------------------------


def test_schema_engine_run_has_required_fields():
    """The EngineRun definition in $defs has properties dict and type=object."""
    stdout = _run_generator_dry_run()
    schema = json.loads(stdout)
    defs = schema["$defs"]
    er_def = defs["EngineRun"]

    assert "properties" in er_def, (
        f"EngineRun $defs entry missing 'properties'. Keys: {list(er_def.keys())}"
    )
    assert isinstance(er_def["properties"], dict), (
        f"EngineRun.properties is not a dict: {type(er_def['properties'])}"
    )
    assert len(er_def["properties"]) > 0, (
        "EngineRun.properties is empty — no fields mapped."
    )

    # type must be "object"
    assert er_def.get("type") == "object", (
        f"EngineRun must have type='object', got {er_def.get('type')!r}"
    )

    # Key EngineRun fields must be present in properties.
    for expected_field in ("run_id", "store_id", "schema_version", "recommendations"):
        assert expected_field in er_def["properties"], (
            f"EngineRun.properties missing expected field '{expected_field}'"
        )


# ---------------------------------------------------------------------------
# Additional structural checks
# ---------------------------------------------------------------------------


def test_schema_defs_includes_key_enums():
    """$defs includes key enums (EvidenceClass, ReasonCode, MechanismType, etc.)."""
    stdout = _run_generator_dry_run()
    schema = json.loads(stdout)
    defs = schema["$defs"]

    for enum_name in ("EvidenceClass", "ReasonCode", "MechanismType", "ModelFitStatus"):
        assert enum_name in defs, (
            f"Expected enum '{enum_name}' in $defs. "
            f"Keys (first 20): {list(defs.keys())[:20]}"
        )
        entry = defs[enum_name]
        assert entry.get("type") == "string", (
            f"{enum_name} in $defs must have type='string', got {entry.get('type')!r}"
        )
        assert "enum" in entry, (
            f"{enum_name} in $defs must have 'enum' list."
        )
        assert len(entry["enum"]) > 0, (
            f"{enum_name}.enum list is empty."
        )


def test_schema_defs_includes_key_dataclasses():
    """$defs includes key dataclasses (PlayCard, RejectedPlay, Audience, etc.)."""
    stdout = _run_generator_dry_run()
    schema = json.loads(stdout)
    defs = schema["$defs"]

    for cls_name in (
        "PlayCard",
        "RejectedPlay",
        "Audience",
        "Measurement",
        "RevenueRange",
        "MonthDelta",
        "ModelCard",
        "StoreProfile",
    ):
        assert cls_name in defs, (
            f"Expected dataclass '{cls_name}' in $defs. "
            f"Keys (first 20): {list(defs.keys())[:20]}"
        )
        entry = defs[cls_name]
        assert entry.get("type") == "object", (
            f"{cls_name} in $defs must have type='object', got {entry.get('type')!r}"
        )
        assert "properties" in entry, (
            f"{cls_name} in $defs must have 'properties'."
        )


def test_schema_mechanism_type_has_all_10_members():
    """MechanismType enum in schema has exactly 10 members (DS §(d) closed set)."""
    stdout = _run_generator_dry_run()
    schema = json.loads(stdout)
    mechanism_type = schema["$defs"]["MechanismType"]
    assert len(mechanism_type["enum"]) == 10, (
        f"MechanismType must have 10 members (DS §(d)); got {mechanism_type['enum']}"
    )


def test_schema_root_ref_points_to_engine_run():
    """Root $ref must point to #/$defs/EngineRun."""
    stdout = _run_generator_dry_run()
    schema = json.loads(stdout)
    assert schema.get("$ref") == "#/$defs/EngineRun", (
        f"Root $ref must be '#/$defs/EngineRun', got {schema.get('$ref')!r}"
    )
