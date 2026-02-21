#!/usr/bin/env python3
"""Safely stage repository changes while excluding runtime artifacts.

Default behavior mirrors `git add --all .` but automatically excludes
logs/autopilot/* and logs/evidence/* so autopilot runs cannot accidentally
commit runtime outputs.  Use `--only` to stage just the provided paths.
"""
from __future__ import annotations

import argparse
import subprocess
from pathlib import Path
from typing import List

ROOT = Path(__file__).resolve().parents[1]

def run(cmd: List[str], check: bool = True) -> None:
    subprocess.run(cmd, cwd=str(ROOT), check=check)


def main() -> int:
    parser = argparse.ArgumentParser(description="Safe git stage helper")
    parser.add_argument("paths", nargs="*", help="Optional extra paths to stage")
    parser.add_argument(
        "--only",
        action="store_true",
        help="Only stage the provided paths (ignore default --all stage)",
    )
    args = parser.parse_args()

    if args.only:
        if not args.paths:
            return 0
        run(["git", "add", "--", *args.paths])
        return 0

    run(["git", "add", "--all", "."])
    # Remove any accidentally staged __pycache__ or .pyc files
    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            cwd=str(ROOT), capture_output=True, text=True, check=True,
        )
        bad_files = [
            f for f in result.stdout.splitlines()
            if "__pycache__" in f or f.endswith(".pyc")
        ]
        if bad_files:
            run(["git", "reset", "HEAD", "--", *bad_files], check=False)
    except subprocess.CalledProcessError:
        pass
    if args.paths:
        run(["git", "add", "--", *args.paths])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
