#!/usr/bin/env python3
"""Business OS — Tech Spec auto-updater.

Checks whether frontend/backend source changed since the last scan and, if so,
re-runs the scanner and refreshes the module index timestamps.

Designed to be run from a cron job (see cronjob tool) or git post-commit hook.

Usage:
    python scripts/tech_spec_update.py [--force]

Exit codes:
    0 — no changes (or updated successfully)
    1 — error
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCAN_DIR = ROOT / "docs" / "tech-spec" / "_scan"
SCANNER = ROOT / "scripts" / "tech_spec_scan.py"
STAMP_FILE = SCAN_DIR / "last_code_hash.txt"

# Paths that affect the tech spec
WATCH_PATHS = [
    "frontend/src/pages",
    "frontend/src/components",
    "frontend/src/services",
    "backend/app/api",
    "backend/app/models",
    "backend/app/schemas",
    "backend/seed_modules.py",
]


def git_hash() -> str:
    # Content hash of the watched tree — identical to the git post-commit hook.
    # Uses blob SHAs from the git index, so it is stable across commits and changes
    # ONLY when watched source content changes (mtime hashing caused a regen loop).
    cmd = ["git", "-C", str(ROOT), "ls-files", "-s", "--", *WATCH_PATHS]
    files = subprocess.run(cmd, capture_output=True, text=True, check=True)
    entries = []
    for line in files.stdout.splitlines():
        parts = line.split()
        if len(parts) < 4:
            continue
        entries.append(f"{parts[1]} {parts[3]}")
    if not entries:
        return "empty"
    import hashlib
    payload = "\n".join(sorted(entries)) + "\n"
    return hashlib.sha1(payload.encode()).hexdigest()[:16]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="always re-scan")
    args = ap.parse_args()

    SCAN_DIR.mkdir(parents=True, exist_ok=True)
    current = git_hash()

    if not args.force and STAMP_FILE.exists():
        prev = STAMP_FILE.read_text().strip()
        if prev == current:
            print("no changes — tech spec is up to date")
            return 0

    # re-scan
    res = subprocess.run(
        [sys.executable, str(SCANNER), "--out", str(SCAN_DIR)],
        capture_output=True, text=True,
    )
    if res.returncode != 0:
        print(f"scanner failed:\n{res.stderr}", file=sys.stderr)
        return 1

    STAMP_FILE.write_text(current)
    summary = json.loads((SCAN_DIR / "summary.json").read_text())
    print(
        f"updated: {summary['pages']} pages, {summary['buttons']} buttons, "
        f"{summary['routes']} routes @ {summary['generated_at']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
