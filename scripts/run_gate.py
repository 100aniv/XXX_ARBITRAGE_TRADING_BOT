#!/usr/bin/env python
"""
SSOT Gate Runner: Core Regression (44 tests)
근거: docs/D92/D92_CORE_REGRESSION_DEFINITION.md
"""

import sys
import subprocess
from pathlib import Path
from datetime import datetime

# Core Regression SSOT (D92 정의)
CORE_REGRESSION_TESTS = [
    "tests/test_d27_monitoring.py",
    "tests/test_d82_0_runner_executor_integration.py",
    "tests/test_d82_2_hybrid_mode.py",
    "tests/test_d92_1_fix_zone_profile_integration.py",
    "tests/test_d92_7_3_zone_profile_ssot.py",
]

PYTEST_ARGS = [
    "--import-mode=importlib",
    "-v",
    "--tb=short",
]


def run_doctor():
    """사전진단: Python, pytest, git 확인"""
    print("\n" + "=" * 80)
    print("doctor: Pre-flight checks")
    print("=" * 80)
    
    # Python 버전
    print(f"\nPython: {sys.version}")
    print(f"Executable: {sys.executable}")
    
    # pytest import
    try:
        import pytest
        print(f"pytest: {pytest.__version__} OK")
    except ImportError:
        print("pytest: FAIL (not installed)")
        return 1
    
    # git status
    try:
        result = subprocess.run(
            ["git", "status", "--short"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent,
        )
        print(f"\ngit status:\n{result.stdout}")
    except Exception as e:
        print(f"git: FAIL ({e})")
        return 1
    
    print("\n✅ doctor: PASS")
    return 0


def run_core_regression(verbose=True):
    """Core Regression SSOT (44 tests)"""
    print("\n" + "=" * 80)
    print("Core Regression SSOT (D92 정의)")
    print("=" * 80)
    
    cmd = [
        sys.executable,
        "-m",
        "pytest",
    ] + CORE_REGRESSION_TESTS + PYTEST_ARGS
    
    if not verbose:
        cmd.append("-q")
    
    print(f"\nCommand: {' '.join(cmd)}\n")
    
    result = subprocess.run(cmd, cwd=Path(__file__).parent.parent)
    
    if result.returncode == 0:
        print("\n✅ Core Regression SSOT: PASS")
    else:
        print("\n❌ Core Regression SSOT: FAIL")
    
    return result.returncode


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/run_gate.py <doctor|fast|regression|full>")
        return 1
    
    mode = sys.argv[1].lower()
    
    if mode == "doctor":
        return run_doctor()
    elif mode in ("fast", "regression"):
        return run_core_regression(verbose=True)
    elif mode == "full":
        print("\n⚠️  full: DEBT/OPTIONAL (not SSOT)")
        print("Use: python -m pytest -q")
        return 0
    else:
        print(f"Unknown mode: {mode}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
