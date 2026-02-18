#!/usr/bin/env python3
"""
DocOps token scan with allowlist policy (Policy A).

Strict targets must be token-free. Allowlist/other targets are count-only.
"""

from __future__ import annotations

import argparse
import fnmatch
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import yaml

DEFAULT_CONFIG = "config/docops_token_allowlist.yml"
DEFAULT_DOCS_DIR = "docs/v2"
DEFAULT_ROADMAP = "D_ROADMAP.md"


@dataclass
class TokenCounts:
    total: int = 0
    strict: int = 0
    allowlist: int = 0
    other: int = 0


@dataclass
class StrictViolation:
    path: str
    token: str
    count: int


def _load_config(config_path: Path) -> Dict[str, object]:
    if not config_path.exists():
        return {}
    with config_path.open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle) or {}
    if not isinstance(payload, dict):
        return {}
    return payload


def _as_posix(path: Path) -> str:
    return str(path).replace("\\", "/")


def _collect_targets(root: Path, docs_dir: str, exts: Iterable[str]) -> List[Path]:
    targets: List[Path] = []
    docs_root = root / docs_dir
    if docs_root.exists():
        for abs_path in docs_root.rglob("*"):
            if abs_path.is_file() and abs_path.suffix in exts:
                targets.append(abs_path)

    roadmap_path = root / DEFAULT_ROADMAP
    if roadmap_path.exists() and roadmap_path.is_file() and roadmap_path.suffix in exts:
        targets.append(roadmap_path)

    return sorted({p.resolve() for p in targets})


def _match_any(path: str, patterns: Iterable[str]) -> bool:
    for pat in patterns:
        if fnmatch.fnmatch(path, pat):
            return True
    return False


def _classify(path: str, strict_patterns: Iterable[str], allow_patterns: Iterable[str]) -> str:
    if _match_any(path, strict_patterns):
        return "strict"
    if _match_any(path, allow_patterns):
        return "allowlist"
    return "other"


def _count_matches(text: str, pattern: re.Pattern[str]) -> int:
    return len(pattern.findall(text))


def main() -> int:
    parser = argparse.ArgumentParser(description="DocOps token policy scan")
    parser.add_argument("--root", default=".", help="Repo root path")
    parser.add_argument("--config", default=DEFAULT_CONFIG, help="Allowlist config path")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    config_path = (root / args.config).resolve()
    config = _load_config(config_path)

    strict_patterns = list(config.get("strict_paths", []))
    allow_patterns = list(config.get("allowlist_paths", []))
    scan_exts = set(config.get("scan_extensions", [".md"]))
    token_patterns = config.get("token_patterns", {})

    compiled_patterns: Dict[str, re.Pattern[str]] = {}
    for key, raw in token_patterns.items():
        compiled_patterns[str(key)] = re.compile(str(raw), re.IGNORECASE)

    targets = _collect_targets(root, DEFAULT_DOCS_DIR, scan_exts)

    counts: Dict[str, TokenCounts] = {name: TokenCounts() for name in compiled_patterns}
    strict_violations: List[StrictViolation] = []

    for abs_path in targets:
        rel_path = _as_posix(abs_path.relative_to(root))
        category = _classify(rel_path, strict_patterns, allow_patterns)
        try:
            text = abs_path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue

        for token_name, pattern in compiled_patterns.items():
            matches = _count_matches(text, pattern)
            if matches <= 0:
                continue
            token_counts = counts[token_name]
            token_counts.total += matches
            if category == "strict":
                token_counts.strict += matches
                strict_violations.append(StrictViolation(rel_path, token_name, matches))
            elif category == "allowlist":
                token_counts.allowlist += matches
            else:
                token_counts.other += matches

    print("[DOCOPS_TOKENS] policy=ALLOWLIST strict=0 required")
    print(f"config={_as_posix(config_path.relative_to(root))}")
    for token_name, token_counts in counts.items():
        print(
            "token={name} total={total} strict={strict} allowlist={allowlist} other={other}".format(
                name=token_name,
                total=token_counts.total,
                strict=token_counts.strict,
                allowlist=token_counts.allowlist,
                other=token_counts.other,
            )
        )

    if strict_violations:
        print("[FAIL] DocOps token policy violation (strict)")
        for violation in strict_violations:
            print(f" - {violation.path} :: {violation.token} ({violation.count})")
        return 1

    print("[PASS] DocOps token policy")
    return 0


if __name__ == "__main__":
    sys.exit(main())
