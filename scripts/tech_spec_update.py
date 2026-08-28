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
    """Hash of the watched source tree (git ls-files + content)."""
    cmd = ["git", "-C", str(ROOT), "ls-files", "--", *WATCH_PATHS]
    files = subprocess.run(cmd, capture_output=True, text=True, check=True)
    names = [f for f in files.stdout.splitlines() if f]
    if not names:
        return "empty"
    # hash file list + mtimes + sizes (fast, no content read)
    import hashlib
    h = hashlib.sha256()
    for name in sorted(names):
        p = ROOT / name
        try:
            st = p.stat()
            h.update(f"{name}:{st.st_mtime_ns}:{st.st_size}\n".encode())
        except FileNotFoundError:
            continue
    return h.hexdigest()[:16]


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
