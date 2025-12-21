"""
D98-7: Open Positions Real-Check 테스트
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


class TestD987OpenPositionsCheck:
    """D98-7 Open Positions 점검 테스트"""
    
    def test_check_open_positions_dryrun(self):
        """Dry-run 모드에서 check_open_positions 실행"""
        from scripts.d98_live_preflight import LivePreflightChecker
        
        checker = LivePreflightChecker(dry_run=True, enable_metrics=False, enable_alerts=False)
        checker.check_open_positions()
        
        # 결과 확인
        assert checker.result.failed == 0
        open_pos_checks = [c for c in checker.result.checks if c["name"] == "Open Positions"]
        assert len(open_pos_checks) == 1
        assert open_pos_checks[0]["status"] == "PASS"
        assert open_pos_checks[0]["details"]["dry_run"] is True
    
    def test_check_open_positions_method_exists(self):
        """check_open_positions 메서드 존재 확인"""
        from scripts.d98_live_preflight import LivePreflightChecker
        
        checker = LivePreflightChecker(dry_run=True, enable_metrics=False, enable_alerts=False)
        assert hasattr(checker, 'check_open_positions')
        assert callable(checker.check_open_positions)
