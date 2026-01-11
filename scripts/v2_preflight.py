#!/usr/bin/env python3
"""
D205-15-6c: V2 Preflight Check Script

목적: 운영 전 60초 내 ops_critical 기능 실제 동작 확인
- Real MarketData 로드 성공
- Redis ping 성공
- DB strict 모드 연결 성공
- 짧은 smoke 실행으로 통합 동작 검증

Exit Code:
- 0: PASS (모든 검증 성공)
- 1: FAIL (하나라도 실패)

Note: PreflightChecker 클래스는 arbitrage/v2/core/preflight_checker.py에 정의됨
"""

import sys
from pathlib import Path
from datetime import datetime

# Add repo root to path
repo_root = Path(__file__).parent.parent
sys.path.insert(0, str(repo_root))

from arbitrage.v2.core.preflight_checker import PreflightChecker


def main():
    """Main entry point"""
    # Evidence 디렉토리 생성
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path(__file__).parent.parent / "logs" / "evidence" / f"v2_preflight_{timestamp}"
    
    checker = PreflightChecker(output_dir)
    
    try:
        success = checker.run_all_checks()
        
        print("")
        print(f"Logs saved: {output_dir / 'preflight.log'}")
        
        return 0 if success else 1
    
    except Exception as e:
        checker.log(f"FATAL ERROR: {e}")
        import traceback
        checker.log(traceback.format_exc())
        return 1


if __name__ == "__main__":
    sys.exit(main())
