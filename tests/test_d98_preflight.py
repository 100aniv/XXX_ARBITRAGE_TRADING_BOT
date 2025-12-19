"""
D98-0: Live Preflight 점검 스크립트 테스트
"""

import os
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

# Import test할 대상 (실제 실행은 하지 않고 mock 처리)
from scripts.d98_live_preflight import (
    PreflightResult,
    LivePreflightChecker,
)


class TestPreflightResult:
    """PreflightResult 클래스 테스트"""
    
    def test_result_initialization(self):
        """결과 초기화"""
        result = PreflightResult()
        
        assert len(result.checks) == 0
        assert result.passed == 0
        assert result.failed == 0
        assert result.warnings == 0
    
    def test_add_check_pass(self):
        """PASS 체크 추가"""
        result = PreflightResult()
        result.add_check("Test", "PASS", "Success")
        
        assert result.passed == 1
        assert result.failed == 0
        assert len(result.checks) == 1
    
    def test_add_check_fail(self):
        """FAIL 체크 추가"""
        result = PreflightResult()
        result.add_check("Test", "FAIL", "Failed")
        
        assert result.passed == 0
        assert result.failed == 1
        assert len(result.checks) == 1
    
    def test_add_check_warn(self):
        """WARN 체크 추가"""
        result = PreflightResult()
        result.add_check("Test", "WARN", "Warning")
        
        assert result.passed == 0
        assert result.failed == 0
        assert result.warnings == 1
    
    def test_is_ready_all_pass(self):
        """모두 PASS면 ready"""
        result = PreflightResult()
        result.add_check("Test1", "PASS", "OK")
        result.add_check("Test2", "PASS", "OK")
        
        assert result.is_ready() is True
    
    def test_is_ready_with_fail(self):
        """FAIL 있으면 not ready"""
        result = PreflightResult()
        result.add_check("Test1", "PASS", "OK")
        result.add_check("Test2", "FAIL", "Error")
        
        assert result.is_ready() is False
    
    def test_to_dict(self):
        """dict 변환"""
        result = PreflightResult()
        result.add_check("Test", "PASS", "OK")
        
        data = result.to_dict()
        
        assert "summary" in data
        assert "checks" in data
        assert "timestamp" in data
        assert data["summary"]["total_checks"] == 1
        assert data["summary"]["passed"] == 1


class TestLivePreflightChecker:
    """LivePreflightChecker 클래스 테스트"""
    
    def setup_method(self):
        """테스트 전 환경변수 정리"""
        # LIVE 관련 환경변수 제거
        for key in ["LIVE_ARM_ACK", "LIVE_ARM_AT", "LIVE_MAX_NOTIONAL_USD"]:
            os.environ.pop(key, None)
    
    def teardown_method(self):
        """테스트 후 환경변수 정리"""
        for key in ["LIVE_ARM_ACK", "LIVE_ARM_AT", "LIVE_MAX_NOTIONAL_USD"]:
            os.environ.pop(key, None)
    
    @patch("scripts.d98_live_preflight.get_settings")
    def test_checker_initialization(self, mock_get_settings):
        """Checker 초기화"""
        mock_settings = MagicMock()
        mock_settings.env = "paper"
        mock_get_settings.return_value = mock_settings
        
        checker = LivePreflightChecker(dry_run=True)
        
        assert checker.dry_run is True
        assert isinstance(checker.result, PreflightResult)
    
    @patch("scripts.d98_live_preflight.get_settings")
    def test_check_environment_paper(self, mock_get_settings):
        """환경 점검 - PAPER 모드"""
        mock_settings = MagicMock()
        mock_settings.env = "paper"
        mock_get_settings.return_value = mock_settings
        
        checker = LivePreflightChecker(dry_run=True)
        checker.check_environment()
        
        assert len(checker.result.checks) == 1
        assert checker.result.checks[0]["status"] == "PASS"
    
    @patch("scripts.d98_live_preflight.get_settings")
    def test_check_environment_live(self, mock_get_settings):
        """환경 점검 - LIVE 모드"""
        mock_settings = MagicMock()
        mock_settings.env = "live"
        mock_get_settings.return_value = mock_settings
        
        checker = LivePreflightChecker(dry_run=True)
        checker.check_environment()
        
        assert len(checker.result.checks) == 1
        assert checker.result.checks[0]["status"] == "WARN"
    
    @patch("scripts.d98_live_preflight.get_settings")
    def test_check_secrets_missing(self, mock_get_settings):
        """시크릿 점검 - 누락"""
        mock_settings = MagicMock()
        mock_settings.env = "paper"
        mock_get_settings.return_value = mock_settings
        
        # 시크릿 제거
        for key in ["UPBIT_ACCESS_KEY", "UPBIT_SECRET_KEY"]:
            os.environ.pop(key, None)
        
        checker = LivePreflightChecker(dry_run=True)
        checker.check_secrets()
        
        assert len(checker.result.checks) == 1
        # 누락된 시크릿이 있으므로 FAIL
        assert checker.result.checks[0]["status"] == "FAIL"
    
    @patch("scripts.d98_live_preflight.get_settings")
    def test_check_database_connection_configured(self, mock_get_settings):
        """DB 연결 점검 - 설정됨"""
        mock_settings = MagicMock()
        mock_settings.env = "paper"
        mock_get_settings.return_value = mock_settings
        
        os.environ["POSTGRES_DSN"] = "postgresql://localhost/test"
        os.environ["REDIS_URL"] = "redis://localhost:6379"
        
        checker = LivePreflightChecker(dry_run=True)
        checker.check_database_connection()
        
        assert len(checker.result.checks) == 1
        assert checker.result.checks[0]["status"] == "PASS"
        
        # Cleanup
        os.environ.pop("POSTGRES_DSN", None)
        os.environ.pop("REDIS_URL", None)
    
    @patch("scripts.d98_live_preflight.get_settings")
    def test_check_database_connection_missing(self, mock_get_settings):
        """DB 연결 점검 - 누락"""
        mock_settings = MagicMock()
        mock_settings.env = "paper"
        mock_get_settings.return_value = mock_settings
        
        # DB 환경변수 제거
        os.environ.pop("POSTGRES_DSN", None)
        os.environ.pop("REDIS_URL", None)
        
        checker = LivePreflightChecker(dry_run=True)
        checker.check_database_connection()
        
        assert len(checker.result.checks) == 1
        assert checker.result.checks[0]["status"] == "FAIL"
    
    @patch("scripts.d98_live_preflight.get_settings")
    def test_check_exchange_health_dryrun(self, mock_get_settings):
        """거래소 Health 점검 - Dry-run"""
        mock_settings = MagicMock()
        mock_settings.env = "paper"
        mock_get_settings.return_value = mock_settings
        
        checker = LivePreflightChecker(dry_run=True)
        checker.check_exchange_health()
        
        assert len(checker.result.checks) == 1
        assert checker.result.checks[0]["status"] == "PASS"
        assert "dry-run" in checker.result.checks[0]["message"]
    
    @patch("scripts.d98_live_preflight.get_settings")
    def test_check_open_positions_dryrun(self, mock_get_settings):
        """오픈 포지션 점검 - Dry-run"""
        mock_settings = MagicMock()
        mock_settings.env = "paper"
        mock_get_settings.return_value = mock_settings
        
        checker = LivePreflightChecker(dry_run=True)
        checker.check_open_positions()
        
        assert len(checker.result.checks) == 1
        assert checker.result.checks[0]["status"] == "PASS"
    
    @patch("scripts.d98_live_preflight.get_settings")
    def test_check_git_safety_no_env_live(self, mock_get_settings):
        """Git 안전 점검 - .env.live 없음"""
        mock_settings = MagicMock()
        mock_settings.env = "paper"
        mock_get_settings.return_value = mock_settings
        
        checker = LivePreflightChecker(dry_run=True)
        checker.check_git_safety()
        
        assert len(checker.result.checks) == 1
        # .env.live 없으면 PASS
        assert checker.result.checks[0]["status"] == "PASS"
