#!/usr/bin/env python3
"""
Guardrail: keep a single welding truth path for execution friction math.

Disallow local helper re-implementations outside:
- arbitrage/v2/domain/pnl_calculator.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple


ROOT = Path(__file__).resolve().parent.parent

ALLOWED_FILES = {
    Path("arbitrage/v2/domain/pnl_calculator.py"),
}

EXCLUDED_DIR_PARTS = {
    ".git",
    "__pycache__",
    ".venv",
    "venv",
    "node_modules",
    ".mypy_cache",
    ".pytest_cache",
}

FORBIDDEN_PATTERNS: Dict[str, re.Pattern[str]] = {
    "local_slippage_helper": re.compile(r"def\s+_calc_slippage_cost\s*\("),
    "local_latency_helper": re.compile(r"def\s+_calc_latency_cost\s*\("),
    "local_partial_helper": re.compile(r"def\s+_calc_partial_penalty\s*\("),
    "local_reject_helper": re.compile(r"def\s+_calc_reject\s*\("),
    "duplicate_truth_api": re.compile(r"def\s+calculate_execution_friction_from_results\s*\("),
    "duplicate_net_pnl_full": re.compile(r"def\s+calculate_net_pnl_full\s*\("),
    "duplicate_net_pnl_welded": re.compile(r"def\s+calculate_net_pnl_full_welded\s*\("),
    "duplicate_friction_breakdown": re.compile(r"def\s+calculate_friction_breakdown\s*\("),
}


def _iter_target_files() -> List[Path]:
    files: List[Path] = []
    for abs_path in ROOT.rglob("*.py"):
        if not abs_path.is_file():
            continue
        rel_path = abs_path.relative_to(ROOT)
        if any(part in EXCLUDED_DIR_PARTS for part in rel_path.parts):
            continue
        files.append(abs_path)
    return sorted(set(files))


def main() -> int:
    violations: List[Tuple[Path, str]] = []

    for abs_path in _iter_target_files():
        rel_path = abs_path.relative_to(ROOT)
        if rel_path in ALLOWED_FILES:
            continue

        try:
            text = abs_path.read_text(encoding="utf-8")
        except Exception:
            continue

        for rule_name, pattern in FORBIDDEN_PATTERNS.items():
            if pattern.search(text):
                violations.append((rel_path, rule_name))

    if violations:
        print("[FAIL] Duplicate PnL/Friction implementation detected")
        for rel_path, rule_name in violations:
            print(f" - {rel_path} :: {rule_name}")
        print("[HINT] Use arbitrage/v2/domain/pnl_calculator.py as the single welding source.")
        return 1

    print("[PASS] Single welding friction path enforced")
    return 0


if __name__ == "__main__":
    sys.exit(main())
