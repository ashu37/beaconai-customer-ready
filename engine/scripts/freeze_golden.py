#!/usr/bin/env python3
"""Freeze golden engine outputs for the Milestone 0 fixture merchants.

Reads the fixture spec at tests/fixtures/merchants.yaml, runs the current
engine end-to-end (CSV -> HTML briefing) against each merchant, and writes
normalized outputs into tests/golden/{merchant_id}/.

Non-deterministic fields are normalized so that re-running the engine on the
same fixture produces byte-identical golden output. The exact normalization
rules live in `_normalize_*` helpers below; if you add a new receipts file or
a new timestamp / run-id field anywhere, extend the matching helper here so
the diff test stays stable.

Usage:
  python scripts/freeze_golden.py                 # dry-run vs existing golden
  python scripts/freeze_golden.py --regenerate    # overwrite tests/golden/
  python scripts/freeze_golden.py --merchant ID   # restrict to one merchant

This script is the *only* sanctioned way to regenerate golden outputs. Any PR
that changes goldens must (a) commit the regenerated tree, and (b) include a
justification line referencing the milestone ticket that authorizes the
behavior change.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, Iterable, List

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURE_PATH = REPO_ROOT / "tests" / "fixtures" / "merchants.yaml"
GOLDEN_ROOT = REPO_ROOT / "tests" / "golden"

# Receipts files we capture into the golden snapshot. Anything not in this
# list is intentionally excluded (e.g., per-run debug CSVs, large chart PNGs,
# segment ZIPs which are non-deterministic in zip metadata).
RECEIPTS_FILES_TO_FREEZE = [
    "run_summary.json",
    "actions_log.json",
    "validation_report.json",
    "engine_validation_report.json",
    "dataframe_debug.json",
    "df_for_charts_counts.json",
]

# ISO-8601 timestamp matcher (date or datetime, with or without TZ / fraction).
_ISO_TS_RE = re.compile(
    r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?"
)


def _is_iso_timestamp(value: str) -> bool:
    return bool(_ISO_TS_RE.fullmatch(value.strip()))


def _strip_run_paths(value: str, run_root: Path) -> str:
    """Replace absolute paths under the per-run output dir with a stable token."""
    run_str = str(run_root)
    private_str = "/private" + run_str if not run_str.startswith("/private") else run_str
    out = value.replace(private_str, "<RUN_ROOT>")
    out = out.replace(run_str, "<RUN_ROOT>")
    return out


def _normalize_json_obj(obj: Any, run_root: Path, key_path: tuple = ()) -> Any:
    """Recursively replace non-deterministic JSON values with stable tokens.

    Rules:
      - Any string that fully matches an ISO-8601 timestamp -> "<TIMESTAMP>"
      - Any string containing the run output path -> "<RUN_ROOT>" prefix
      - Any dict key in the well-known timestamp set -> value replaced
        unconditionally (covers cases where the value isn't a pure ISO match,
        e.g., naive datetimes printed by str()).
    """
    timestamp_keys = {
        "ts",
        "timestamp",
        "validation_timestamp",
        "generated_at",
        "run_id",
        "updated_at",
    }
    if isinstance(obj, dict):
        out: Dict[str, Any] = {}
        for k, v in obj.items():
            if k in timestamp_keys:
                out[k] = "<TIMESTAMP>" if k != "run_id" else "<RUN_ID>"
            else:
                out[k] = _normalize_json_obj(v, run_root, key_path + (k,))
        return out
    if isinstance(obj, list):
        return [_normalize_json_obj(v, run_root, key_path) for v in obj]
    if isinstance(obj, str):
        s = obj
        # Path stripping first, then timestamp replacement on the remainder.
        s_stripped = _strip_run_paths(s, run_root)
        if _is_iso_timestamp(s_stripped):
            return "<TIMESTAMP>"
        return s_stripped
    return obj


def _normalize_html(html: str, run_root: Path) -> str:
    out = _strip_run_paths(html, run_root)
    # Replace any inline ISO-8601 timestamp occurrences in HTML text.
    out = _ISO_TS_RE.sub("<TIMESTAMP>", out)
    return out


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, indent=2, sort_keys=True, default=str),
        encoding="utf-8",
    )


def _load_fixtures(only: List[str] | None = None) -> List[Dict[str, Any]]:
    spec = yaml.safe_load(FIXTURE_PATH.read_text())
    merchants = spec.get("merchants", []) or []
    if only:
        wanted = set(only)
        merchants = [m for m in merchants if m.get("id") in wanted]
        missing = wanted - {m.get("id") for m in merchants}
        if missing:
            raise SystemExit(f"Unknown merchant id(s): {sorted(missing)}")
    return merchants


def _run_engine(merchant: Dict[str, Any], out_dir: Path) -> None:
    """Invoke the engine end-to-end for one merchant.

    Imports happen here rather than at module top because importing
    src.main triggers .env loading and pulls heavy deps; we only want that
    cost when actually running.
    """
    from src.main import run

    csv_rel = merchant["csv"]
    brand = merchant.get("brand") or merchant["id"]
    csv_path = REPO_ROOT / csv_rel
    if not csv_path.exists():
        raise FileNotFoundError(f"Fixture CSV missing: {csv_path}")
    out_dir.mkdir(parents=True, exist_ok=True)
    run(str(csv_path), brand, str(out_dir))


def _capture_outputs(run_dir: Path, brand: str, dest: Path) -> None:
    """Copy + normalize engine outputs from run_dir into dest (golden tree)."""
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True, exist_ok=True)

    # --- briefing HTML
    briefing_src = run_dir / "briefings" / f"{brand}_briefing.html"
    if briefing_src.exists():
        html = briefing_src.read_text(encoding="utf-8")
        (dest / "briefing.html").write_text(
            _normalize_html(html, run_dir), encoding="utf-8"
        )

    # --- receipts JSON files (whitelist)
    receipts_dest = dest / "receipts"
    receipts_dest.mkdir(parents=True, exist_ok=True)
    for fname in RECEIPTS_FILES_TO_FREEZE:
        src = run_dir / "receipts" / fname
        if not src.exists():
            continue
        try:
            data = json.loads(src.read_text(encoding="utf-8"))
        except Exception as e:
            # Capture parse error as a record so the test surfaces it.
            data = {"__parse_error__": str(e)}
        normalized = _normalize_json_obj(data, run_dir)
        _write_json(receipts_dest / fname, normalized)


def _diff_paths(a: Path, b: Path) -> str:
    """Return a unified diff string between two text files (empty if equal)."""
    import difflib

    a_text = a.read_text(encoding="utf-8") if a.exists() else ""
    b_text = b.read_text(encoding="utf-8") if b.exists() else ""
    if a_text == b_text:
        return ""
    diff = difflib.unified_diff(
        a_text.splitlines(keepends=True),
        b_text.splitlines(keepends=True),
        fromfile=str(a),
        tofile=str(b),
        n=3,
    )
    return "".join(diff)


def freeze_one(merchant: Dict[str, Any], regenerate: bool) -> Dict[str, Any]:
    merchant_id = merchant["id"]
    brand = merchant.get("brand") or merchant_id
    dest = GOLDEN_ROOT / merchant_id
    with tempfile.TemporaryDirectory(prefix=f"beaconai_freeze_{merchant_id}_") as tmp:
        run_dir = Path(tmp)
        print(f"[freeze] running engine for {merchant_id} -> {run_dir}")
        _run_engine(merchant, run_dir)

        if regenerate:
            print(f"[freeze] writing golden -> {dest}")
            _capture_outputs(run_dir, brand, dest)
            return {"merchant": merchant_id, "status": "regenerated", "diff": ""}

        # Dry-run: capture into a sibling temp dir and diff vs golden.
        with tempfile.TemporaryDirectory(prefix=f"beaconai_check_{merchant_id}_") as tmp2:
            check_dest = Path(tmp2) / merchant_id
            _capture_outputs(run_dir, brand, check_dest)
            diff_chunks: List[str] = []
            # Walk both trees and diff every file under golden/.
            golden_files = (
                {p.relative_to(dest) for p in dest.rglob("*") if p.is_file()}
                if dest.exists()
                else set()
            )
            check_files = {
                p.relative_to(check_dest) for p in check_dest.rglob("*") if p.is_file()
            }
            for rel in sorted(golden_files | check_files):
                gpath = dest / rel
                cpath = check_dest / rel
                d = _diff_paths(gpath, cpath)
                if d:
                    diff_chunks.append(d)
            return {
                "merchant": merchant_id,
                "status": "ok" if not diff_chunks else "diff",
                "diff": "\n".join(diff_chunks),
            }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    ap.add_argument(
        "--regenerate",
        action="store_true",
        help="Overwrite tests/golden/ with newly captured outputs.",
    )
    ap.add_argument(
        "--merchant",
        action="append",
        help="Restrict to one or more merchant ids (repeatable).",
    )
    args = ap.parse_args()

    # Make repo root the cwd so relative paths in get_config / .env behave the
    # same as a normal CLI invocation.
    os.chdir(REPO_ROOT)
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))

    merchants = _load_fixtures(args.merchant)
    if not merchants:
        print("No merchants matched.", file=sys.stderr)
        return 2

    GOLDEN_ROOT.mkdir(parents=True, exist_ok=True)
    results = [freeze_one(m, args.regenerate) for m in merchants]

    bad = [r for r in results if r["status"] == "diff"]
    if args.regenerate:
        print(f"[freeze] regenerated {len(results)} merchant(s).")
        return 0
    if bad:
        for r in bad:
            print(f"\n=== DRIFT for {r['merchant']} ===")
            print(r["diff"][:8000])
            if len(r["diff"]) > 8000:
                print(f"... [{len(r['diff']) - 8000} more chars]")
        print(
            f"[freeze] {len(bad)}/{len(results)} merchant(s) drifted.",
            file=sys.stderr,
        )
        return 1
    print(f"[freeze] all {len(results)} merchant(s) match golden.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
