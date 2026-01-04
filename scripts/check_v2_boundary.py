#!/usr/bin/env python3
import ast
import sys
from pathlib import Path

# ===== 설정 =====
V2_ROOT = Path("arbitrage/v2")
FORBIDDEN_PREFIXES = (
    "arbitrage.execution",   # V1 execution
    "arbitrage.v1",          # V1 namespace
)

ALLOWLIST_PREFIXES = (
    "arbitrage.v2",
    "arbitrage.common",
)

def is_forbidden(module: str) -> bool:
    if module.startswith(ALLOWLIST_PREFIXES):
        return False
    return module.startswith(FORBIDDEN_PREFIXES)

def scan_file(path: Path):
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"[PARSE ERROR] {path}: {e}")
        return [(path, "PARSE_ERROR")]

    violations = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if is_forbidden(alias.name):
                    violations.append((path, alias.name))

        elif isinstance(node, ast.ImportFrom):
            if node.module and is_forbidden(node.module):
                violations.append((path, node.module))

    return violations

def main():
    violations = []

    for py in V2_ROOT.rglob("*.py"):
        violations.extend(scan_file(py))

    if violations:
        print("\n[V2 BOUNDARY VIOLATION DETECTED]")
        for path, module in violations:
            print(f" - {path}: imports forbidden module '{module}'")
        print("\nFAIL: V2 must not import V1 execution paths.")
        sys.exit(1)

    print("PASS: V2/V1 boundary clean.")
    sys.exit(0)

if __name__ == "__main__":
    main()
