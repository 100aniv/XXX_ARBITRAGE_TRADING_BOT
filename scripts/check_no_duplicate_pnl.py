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

FORBIDDEN_PATTERNS: Dict[str, re.Pattern[str]] = {
    "local_slippage_helper": re.compile(r"def\s+_calc_slippage_cost\s*\("),
    "local_latency_helper": re.compile(r"def\s+_calc_latency_cost\s*\("),
    "local_partial_helper": re.compile(r"def\s+_calc_partial_penalty\s*\("),
    "local_reject_helper": re.compile(r"def\s+_calc_reject\s*\("),
    "duplicate_truth_api": re.compile(r"def\s+calculate_execution_friction_from_results\s*\("),
}


def _iter_target_files() -> List[Path]:
    files: List[Path] = []
    for pattern in ("arbitrage/**/*.py", "scripts/**/*.py"):
        files.extend(ROOT.glob(pattern))
    return sorted({path for path in files if path.is_file()})


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
