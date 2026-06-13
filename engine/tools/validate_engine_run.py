#!/usr/bin/env python
"""Round-trip validation tool for engine_run.json against schemas/engine_run.v2.json.

S13.7-T2.

Usage
-----
    python tools/validate_engine_run.py data/<store_id>/runs/<run_id>.json

Exit codes:
    0  PASS — the file validates against schemas/engine_run.v2.json.
    1  FAIL — validation errors reported, or schema / file missing.

The ``jsonschema`` library is used for validation.  It is a soft dependency:
if not installed, a clear error message is printed and the tool exits with
code 1 (rather than crashing with ImportError).

To install if absent:
    pip install jsonschema
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Path setup — allow running from repo root without installing the package.
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT))

_SCHEMA_PATH = _REPO_ROOT / "schemas" / "engine_run.v2.json"


def _load_json(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def validate(engine_run_path: Path) -> bool:
    """Validate ``engine_run_path`` against the generated schema.

    Returns True on PASS, False on FAIL.  Prints errors to stdout.
    """

    # Soft-import jsonschema.
    try:
        import jsonschema
    except ImportError:
        print(
            "FAIL: 'jsonschema' is not installed. "
            "Install it with: pip install jsonschema"
        )
        return False

    # Load the schema.
    if not _SCHEMA_PATH.exists():
        print(
            f"FAIL: Schema file not found at {_SCHEMA_PATH}. "
            "Run: python tools/generate_schema.py"
        )
        return False

    try:
        schema = _load_json(_SCHEMA_PATH)
    except Exception as e:
        print(f"FAIL: Could not load schema from {_SCHEMA_PATH}: {e}")
        return False

    # Load the engine_run.json.
    if not engine_run_path.exists():
        print(f"FAIL: engine_run.json not found at {engine_run_path}")
        return False

    try:
        instance = _load_json(engine_run_path)
    except Exception as e:
        print(f"FAIL: Could not parse {engine_run_path}: {e}")
        return False

    # Validate.
    validator_cls = jsonschema.Draft7Validator
    validator = validator_cls(schema)
    errors = sorted(validator.iter_errors(instance), key=lambda e: list(e.path))

    if errors:
        print(f"FAIL: {len(errors)} validation error(s) in {engine_run_path}:")
        for err in errors[:20]:  # cap output at 20 errors
            path_str = " -> ".join(str(p) for p in err.path) if err.path else "(root)"
            print(f"  [{path_str}] {err.message}")
        if len(errors) > 20:
            print(f"  ... and {len(errors) - 20} more error(s) (output capped at 20)")
        return False

    print(f"PASS: {engine_run_path} validates against {_SCHEMA_PATH}")
    return True


def main() -> None:
    if len(sys.argv) < 2:
        print(
            "Usage: python tools/validate_engine_run.py "
            "data/<store_id>/runs/<run_id>.json"
        )
        sys.exit(1)

    engine_run_path = Path(sys.argv[1])
    passed = validate(engine_run_path)
    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
