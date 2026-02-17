#!/usr/bin/env python3
"""
Guardrail: keep scripts/harness as power-button thin wrappers.

Policy:
- Selected files must be thin wrappers at all times.
- For changed Python files under scripts/ or arbitrage/v2/harness/,
  business-logic style structure (class/loop-heavy code) is forbidden
  unless explicitly allowlisted.
"""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path
from typing import Iterable, List, Set, Tuple


ROOT = Path(__file__).resolve().parent.parent

THIN_WRAPPER_REQUIRED: Set[Path] = {
    Path("scripts/run_d205_8_topn_stress.py"),
    Path("arbitrage/v2/harness/topn_stress.py"),
}

ALLOWLIST_CHANGED_NON_THIN: Set[Path] = {
    Path("scripts/run_gate_with_evidence.py"),
    Path("scripts/check_engine_centricity.py"),
    Path("scripts/check_no_duplicate_pnl.py"),
}


def _git_changed_files() -> List[Path]:
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
    except Exception:
        return []

    changed: List[Path] = []
    for raw in result.stdout.splitlines():
        line = raw.rstrip("\n")
        if not line:
            continue
        path_token = line[3:]
        if " -> " in path_token:
            path_token = path_token.split(" -> ", 1)[1]
        candidate = Path(path_token.strip())
        if candidate.suffix == ".py":
            changed.append(candidate)
    return changed


def _is_target_path(path: Path) -> bool:
    text = str(path).replace("\\", "/")
    return text.startswith("scripts/") or text.startswith("arbitrage/v2/harness/")


def _read_ast(path: Path) -> ast.AST:
    text = (ROOT / path).read_text(encoding="utf-8")
    return ast.parse(text)


def _is_thin_wrapper(path: Path) -> Tuple[bool, str]:
    try:
        tree = _read_ast(path)
    except Exception as exc:
        return False, f"parse_error:{exc}"

    class_count = sum(isinstance(n, ast.ClassDef) for n in ast.walk(tree))
    func_defs = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]
    loop_count = sum(isinstance(n, (ast.For, ast.While)) for n in ast.walk(tree))

    if class_count > 0:
        return False, f"class_defs={class_count}"

    allowed_function_names = {"main", "cli_main"}
    if any(fn.name not in allowed_function_names for fn in func_defs):
        bad = sorted({fn.name for fn in func_defs if fn.name not in allowed_function_names})
        return False, f"non_wrapper_functions={bad}"

    if loop_count > 0:
        return False, f"loops={loop_count}"

    return True, "ok"


def _assert_required_wrappers() -> List[str]:
    violations: List[str] = []
    for rel_path in sorted(THIN_WRAPPER_REQUIRED):
        abs_path = ROOT / rel_path
        if not abs_path.exists():
            violations.append(f"missing_required_wrapper:{rel_path}")
            continue
        ok, reason = _is_thin_wrapper(rel_path)
        if not ok:
            violations.append(f"non_thin_required_wrapper:{rel_path}:{reason}")
    return violations


def _assert_changed_files() -> List[str]:
    violations: List[str] = []
    for rel_path in _git_changed_files():
        if not _is_target_path(rel_path):
            continue
        if rel_path in ALLOWLIST_CHANGED_NON_THIN:
            continue
        abs_path = ROOT / rel_path
        if not abs_path.exists():
            continue
        ok, reason = _is_thin_wrapper(rel_path)
        if not ok:
            violations.append(f"changed_non_thin:{rel_path}:{reason}")
    return violations


def main() -> int:
    violations = []
    violations.extend(_assert_required_wrappers())
    violations.extend(_assert_changed_files())

    if violations:
        print("[FAIL] Engine-centricity guard failed")
        for item in violations:
            print(f" - {item}")
        print("[HINT] Move business logic into arbitrage/v2/core or arbitrage/v2/domain.")
        return 1

    print("[PASS] Engine-centricity guard passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
