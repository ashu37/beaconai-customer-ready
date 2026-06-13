#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path


def _copy_tree(src: Path, dest: Path, dry_run: bool) -> None:
    if not src.exists():
        return
    if dest.exists():
        if dry_run:
            print(f"[dry-run] remove {dest}")
        else:
            shutil.rmtree(dest)
    if dry_run:
        print(f"[dry-run] copytree {src} -> {dest}")
        return
    shutil.copytree(src, dest)


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync a generated briefing + assets into beaconai-frontend sample-report folder.")
    parser.add_argument("--brand", required=True, help="Brand name used in the output filename (e.g., YOUR_BRAND)")
    parser.add_argument(
        "--out-dir",
        default=None,
        help="Path to analysis output root for the brand (defaults to <repo>/analysis/<brand>)",
    )
    parser.add_argument(
        "--dest",
        default=None,
        help="Destination folder (defaults to ../beaconai-frontend/public/reports/sample-report)",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print actions without copying files")

    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    analysis_root = Path(args.out_dir) if args.out_dir else repo_root / "analysis" / args.brand
    briefing_dir = analysis_root / "briefings"
    briefing_file = briefing_dir / f"{args.brand}_briefing.html"

    default_dest = repo_root.parent / "beaconai-frontend" / "public" / "reports" / "sample-report"
    dest_dir = Path(args.dest) if args.dest else default_dest

    if not briefing_file.exists():
        print(f"error: briefing not found: {briefing_file}")
        return 1

    if args.dry_run:
        print(f"[dry-run] ensure {dest_dir}")
    else:
        dest_dir.mkdir(parents=True, exist_ok=True)

    # Copy briefing HTML
    briefing_dest = dest_dir / "briefing.html"
    if args.dry_run:
        print(f"[dry-run] copy {briefing_file} -> {briefing_dest}")
    else:
        shutil.copy2(briefing_file, briefing_dest)

    # Copy charts and assets (overwrite subfolders)
    _copy_tree(briefing_dir / "charts", dest_dir / "charts", args.dry_run)
    _copy_tree(briefing_dir / "assets", dest_dir / "assets", args.dry_run)

    print("Sync complete.")
    print(f"- HTML: {briefing_dest}")
    if (dest_dir / "charts").exists() or args.dry_run:
        print(f"- Charts: {dest_dir / 'charts'}")
    if (dest_dir / "assets").exists() or args.dry_run:
        print(f"- Assets: {dest_dir / 'assets'}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
