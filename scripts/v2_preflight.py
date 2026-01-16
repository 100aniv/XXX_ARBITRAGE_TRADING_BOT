#!/usr/bin/env python3
"""
D206-0: V2 Preflight Check Script (Artifact-First)

목적: engine_report.json 기반 검증 (Runner 참조 금지)
- Schema validation (필수 필드 존재)
- Gate validation (warnings=0, skips=0, errors=0)
- Wallclock drift (±5% 이내)
- DB integrity (closed_trades × 3 ≈ inserts_ok)
- Exit code (0=PASS, 1=FAIL)

Exit Code:
- 0: PASS (모든 검증 성공)
- 1: FAIL (하나라도 실패)

Usage:
    python scripts/v2_preflight.py <evidence_dir>
    
Example:
    python scripts/v2_preflight.py logs/evidence/d206_0_gate_restore_20260116_203000
"""

import sys
import logging
from pathlib import Path

# Add repo root to path
repo_root = Path(__file__).parent.parent
sys.path.insert(0, str(repo_root))

from arbitrage.v2.core.preflight_checker import PreflightChecker

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


def main():
    """Main entry point"""
    if len(sys.argv) < 2:
        print("Usage: python scripts/v2_preflight.py <evidence_dir>")
        print("Example: python scripts/v2_preflight.py logs/evidence/d206_0_gate_restore_20260116_203000")
        return 1
    
    evidence_dir = Path(sys.argv[1])
    
    if not evidence_dir.exists():
        print(f"ERROR: Evidence directory not found: {evidence_dir}")
        return 1
    
    checker = PreflightChecker(evidence_dir)
    
    try:
        success = checker.run_all_checks()
        return 0 if success else 1
    
    except Exception as e:
        logging.error(f"FATAL ERROR: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
