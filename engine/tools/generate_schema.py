#!/usr/bin/env python
"""Hand-written JSON Schema (draft-07) generator for src/engine_run.py.

S13.7-T2 — DS adjudication #6: hand-written generator; dataclasses-jsonschema
and pydantic are explicitly rejected.

Usage
-----
Write schemas/engine_run.v2.json:

    python tools/generate_schema.py

Dry-run (print to stdout instead of writing):

    python tools/generate_schema.py --dry-run

The generator walks every dataclass exported in ``src.engine_run.__all__``
plus the dataclasses needed by EngineRun that live in re-exported modules
(StoreProfile, ModelCard, RetentionCard) and emits a JSON Schema draft-07
document with all schemas in ``$defs`` and a root ``$ref`` to EngineRun.

Type mapping (conservative / useful-for-agents):
  str                  -> {"type": "string"}
  int                  -> {"type": "integer"}
  float                -> {"type": "number"}
  bool                 -> {"type": "boolean"}
  Optional[X]          -> {"oneOf": [<X schema>, {"type": "null"}]}
  List[X]              -> {"type": "array", "items": <X schema>}
  Dict[str, X]         -> {"type": "object", "additionalProperties": <X schema>}
  Literal["x"]         -> {"type": "string", "enum": ["x"]}
  Enum subclass        -> {"type": "string", "enum": [<member values>]}
  Another dataclass    -> {"$ref": "#/$defs/<ClassName>"}
  Tuple[...]           -> {"type": "array"}          (open — Tuples are arrays)
  Any / unknown        -> {}                          (open schema)
"""

from __future__ import annotations

import argparse
import inspect
import json
import re
import sys
from dataclasses import fields, is_dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Dict, get_type_hints

# ---------------------------------------------------------------------------
# Path setup — allow running from repo root without installing the package.
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT))

# ---------------------------------------------------------------------------
# Import the schema authority module.
# ---------------------------------------------------------------------------
import src.engine_run as _er  # noqa: E402

# Additional dataclasses re-exported by engine_run but defined elsewhere.
from src.profile.types import StoreProfile  # noqa: E402
from src.predictive.model_card import (  # noqa: E402
    ModelCard,
    RetentionCard,
    SegmentBand,
)

# ---------------------------------------------------------------------------
# Registry: every dataclass + enum that may appear in the schema.
# We build this from engine_run's __all__ plus the extra dataclasses
# transitively reachable from EngineRun.
# ---------------------------------------------------------------------------

# Enums and dataclasses defined directly in src.engine_run.
_ENGINE_RUN_ENUMS = {
    name: getattr(_er, name)
    for name in dir(_er)
    if isinstance(getattr(_er, name, None), type)
    and issubclass(getattr(_er, name), Enum)
    and getattr(_er, name).__module__ == _er.__name__
}

_ENGINE_RUN_DATACLASSES = {
    name: getattr(_er, name)
    for name in dir(_er)
    if isinstance(getattr(_er, name, None), type)
    and is_dataclass(getattr(_er, name))
    and getattr(_er, name).__module__ == _er.__name__
}

# Additional re-exported dataclasses from sub-modules.
_EXTRA_DATACLASSES: Dict[str, type] = {
    "StoreProfile": StoreProfile,
    "ModelCard": ModelCard,
    "RetentionCard": RetentionCard,
    # S-FE-rfm-segment-distribution: SegmentBand is referenced by
    # ModelCard.segment_distribution (List[SegmentBand]); register it so the
    # $ref resolves.
    "SegmentBand": SegmentBand,
}

# Enums from the sub-modules (referenced by re-exported dataclasses).
from src.predictive.model_card import (  # noqa: E402
    ModelFitStatus,
    RfmSegmentDistributionSuppressionReason,
)

_EXTRA_ENUMS: Dict[str, type] = {
    "ModelFitStatus": ModelFitStatus,
    # S-FE-rfm-segment-distribution: paired RULE-A null-reason referenced by
    # ModelCard.segment_distribution_suppression_reason.
    "RfmSegmentDistributionSuppressionReason": RfmSegmentDistributionSuppressionReason,
}

# Merge all registries.
_ALL_DATACLASSES: Dict[str, type] = {**_ENGINE_RUN_DATACLASSES, **_EXTRA_DATACLASSES}
_ALL_ENUMS: Dict[str, type] = {**_ENGINE_RUN_ENUMS, **_EXTRA_ENUMS}


# ---------------------------------------------------------------------------
# Type-string → JSON Schema converter
# ---------------------------------------------------------------------------

def _type_str_to_schema(type_str: str) -> dict:
    """Map a field type annotation string to a JSON Schema fragment."""

    s = type_str.strip()

    # Strip outer quotes (forward-reference strings like "'RevenueRange'").
    if s.startswith("'") and s.endswith("'"):
        s = s[1:-1]

    # Optional[X] → oneOf: [X schema, null]
    m_optional = re.fullmatch(r"Optional\[(.+)\]", s)
    if m_optional:
        inner = _type_str_to_schema(m_optional.group(1))
        return {"oneOf": [inner, {"type": "null"}]}

    # List[X] → array with items
    m_list = re.fullmatch(r"List\[(.+)\]", s)
    if m_list:
        items = _type_str_to_schema(m_list.group(1))
        return {"type": "array", "items": items}

    # Dict[str, X] → object with additionalProperties
    m_dict = re.fullmatch(r"Dict\[str,\s*(.+)\]", s)
    if m_dict:
        value_schema = _type_str_to_schema(m_dict.group(1))
        return {"type": "object", "additionalProperties": value_schema}

    # Tuple[...] → array (open)
    if s.startswith("Tuple["):
        return {"type": "array"}

    # Literal["x"] or Literal['x']
    m_literal = re.fullmatch(r"""Literal\[['"](.+)['"]\]""", s)
    if m_literal:
        return {"type": "string", "enum": [m_literal.group(1)]}

    # Primitive types
    _PRIMITIVES: Dict[str, dict] = {
        "str": {"type": "string"},
        "int": {"type": "integer"},
        "float": {"type": "number"},
        "bool": {"type": "boolean"},
        "Any": {},
    }
    if s in _PRIMITIVES:
        return _PRIMITIVES[s]

    # Known enum → string enum with values
    if s in _ALL_ENUMS:
        enum_cls = _ALL_ENUMS[s]
        return {"type": "string", "enum": [m.value for m in enum_cls]}

    # Known dataclass → $ref
    if s in _ALL_DATACLASSES:
        return {"$ref": f"#/$defs/{s}"}

    # Fallback: open schema (any)
    return {}


def _has_default(fld) -> bool:
    """Return True if the field has a default value (i.e. it is optional in JSON)."""
    import dataclasses
    return (
        fld.default is not dataclasses.MISSING
        or fld.default_factory is not dataclasses.MISSING  # type: ignore[misc]
    )


def _dataclass_to_schema(cls: type) -> dict:
    """Emit a JSON Schema object for a dataclass."""

    properties: Dict[str, dict] = {}
    required: list = []

    flds = fields(cls)
    for fld in flds:
        # Use the string annotation (matches what dataclasses stores at runtime
        # with from __future__ import annotations in the source module).
        type_str = str(fld.type) if fld.type is not None else "Any"
        properties[fld.name] = _type_str_to_schema(type_str)
        if not _has_default(fld):
            required.append(fld.name)

    schema: dict = {
        "type": "object",
        "properties": properties,
    }
    if required:
        schema["required"] = required

    return schema


# ---------------------------------------------------------------------------
# Schema assembly
# ---------------------------------------------------------------------------

def generate_schema() -> dict:
    """Generate the full JSON Schema document."""

    defs: Dict[str, dict] = {}

    # 1. All enums (engine_run + extras)
    for name, cls in sorted(_ALL_ENUMS.items()):
        defs[name] = {"type": "string", "enum": [m.value for m in cls]}

    # 2. All dataclasses (engine_run + extras)
    for name, cls in sorted(_ALL_DATACLASSES.items()):
        defs[name] = _dataclass_to_schema(cls)

    schema = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "title": "EngineRun v2.1.0",
        "$ref": "#/$defs/EngineRun",
        "$defs": defs,
    }
    return schema


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Generate schemas/engine_run.v2.json from src/engine_run.py dataclasses. "
            "S13.7-T2 hand-written generator (DS adjudication #6 — no new deps)."
        )
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the schema to stdout instead of writing to disk.",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    schema = generate_schema()
    schema_json = json.dumps(schema, indent=2, ensure_ascii=False)

    if args.dry_run:
        print(schema_json)
        return

    schemas_dir = _REPO_ROOT / "schemas"
    schemas_dir.mkdir(parents=True, exist_ok=True)

    out_path = schemas_dir / "engine_run.v2.json"
    out_path.write_text(schema_json + "\n", encoding="utf-8")
    print(f"[generate_schema] Written: {out_path}")


if __name__ == "__main__":
    main()
