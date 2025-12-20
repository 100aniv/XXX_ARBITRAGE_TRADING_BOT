"""
D98-5: Preflight Real-Check 테스트

Redis/Postgres/Exchange 실제 연결 검증 테스트.
"""

import os
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from arbitrage.config.preflight import PreflightError
from scripts.d98_live_preflight import LivePreflightChecker, PreflightResult


class TestPreflightRealCheck:
    """Preflight Real-Check 단위 테스트"""
    
    @patch.dict(os.environ, {
        "ARBITRAGE_ENV": "paper",
        "READ_ONLY_ENFORCED": "true",
        "POSTGRES_DSN": "postgresql://test:test@localhost:5432/test",
        "REDIS_URL": "redis://localhost:6380/0",
        "UPBIT_ACCESS_KEY": "test_key",
        "UPBIT_SECRET_KEY": "test_secret",
        "BINANCE_API_KEY": "test_key",
        "BINANCE_API_SECRET": "test_secret",
        "TELEGRAM_BOT_TOKEN": "test_token",
        "TELEGRAM_CHAT_ID": "test_id",
    }, clear=True)
    def test_preflight_dry_run_pass(self):
        """Dry-run 모드: 환경변수만 확인 → PASS"""
        checker = LivePreflightChecker(dry_run=True)
        result = checker.run_all_checks()
        
        assert result.is_ready() is True
        assert result.failed == 0
        
        # Database check가 dry-run으로 PASS
        db_check = [c for c in result.checks if c["name"] == "Database"][0]
        assert db_check["status"] == "PASS"
        assert db_check["details"]["dry_run"] is True
    
    @patch.dict(os.environ, {
        "ARBITRAGE_ENV": "paper",
        "READ_ONLY_ENFORCED": "true",
        "UPBIT_ACCESS_KEY": "test_key",
        "UPBIT_SECRET_KEY": "test_secret",
        "BINANCE_API_KEY": "test_key",
        "BINANCE_API_SECRET": "test_secret",
        "TELEGRAM_BOT_TOKEN": "test_token",
        "TELEGRAM_CHAT_ID": "test_id",
    }, clear=True)
    def test_preflight_missing_db_config(self):
        """DB 환경변수 누락 → FAIL"""
        # POSTGRES_DSN, REDIS_URL 누락
        checker = LivePreflightChecker(dry_run=True)
        result = checker.run_all_checks()
        
        assert result.is_ready() is False
        assert result.failed >= 1
        
        # Database check가 FAIL
        db_check = [c for c in result.checks if c["name"] == "Database"][0]
        assert db_check["status"] == "FAIL"
        assert "missing" in db_check["details"]
    
    @patch.dict(os.environ, {
        "ARBITRAGE_ENV": "paper",
        "READ_ONLY_ENFORCED": "true",
        "POSTGRES_DSN": "postgresql://arbitrage:arbitrage@localhost:5432/arbitrage",
        "REDIS_URL": "redis://localhost:6380/0",
        "UPBIT_ACCESS_KEY": "test_key",
        "UPBIT_SECRET_KEY": "test_secret",
        "BINANCE_API_KEY": "test_key",
        "BINANCE_API_SECRET": "test_secret",
        "TELEGRAM_BOT_TOKEN": "test_token",
        "TELEGRAM_CHAT_ID": "test_id",
    }, clear=True)
    @patch("redis.from_url")
    @patch("psycopg2.connect")
    def test_preflight_realcheck_redis_postgres_pass(self, mock_pg_connect, mock_redis):
        """Real-Check: Redis + Postgres 정상 연결 → PASS"""
        # Mock Redis
        mock_redis_client = MagicMock()
        mock_redis_client.ping.return_value = True
        mock_redis_client.get.return_value = b"ok"
        mock_redis_client.set.return_value = True
        mock_redis_client.delete.return_value = 1
        mock_redis.return_value = mock_redis_client
        
        # Mock Postgres
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (1,)
        mock_conn.cursor.return_value = mock_cursor
        mock_pg_connect.return_value = mock_conn
        
        # Real-Check 실행
        checker = LivePreflightChecker(dry_run=False)
        result = checker.run_all_checks()
        
        assert result.is_ready() is True
        assert result.failed == 0
        
        # Database check가 PASS
        db_check = [c for c in result.checks if c["name"] == "Database"][0]
        assert db_check["status"] == "PASS"
        assert db_check["details"]["real_check"] is True
        assert db_check["details"]["redis"] == "connected"
        assert db_check["details"]["postgres"] == "connected"
    
    @patch.dict(os.environ, {
        "ARBITRAGE_ENV": "paper",
        "READ_ONLY_ENFORCED": "true",
        "POSTGRES_DSN": "postgresql://arbitrage:arbitrage@localhost:5432/arbitrage",
        "REDIS_URL": "redis://localhost:6380/0",
        "UPBIT_ACCESS_KEY": "test_key",
        "UPBIT_SECRET_KEY": "test_secret",
        "BINANCE_API_KEY": "test_key",
        "BINANCE_API_SECRET": "test_secret",
        "TELEGRAM_BOT_TOKEN": "test_token",
        "TELEGRAM_CHAT_ID": "test_id",
    }, clear=True)
    @patch("redis.from_url")
    def test_preflight_realcheck_redis_fail(self, mock_redis):
        """Real-Check: Redis 연결 실패 → FAIL"""
        # Mock Redis failure
        mock_redis.side_effect = Exception("Connection refused")
        
        # Real-Check 실행
        checker = LivePreflightChecker(dry_run=False)
        result = checker.run_all_checks()
        
        assert result.is_ready() is False
        assert result.failed >= 1
        
        # Database check가 FAIL
        db_check = [c for c in result.checks if c["name"] == "Database"][0]
        assert db_check["status"] == "FAIL"
        assert "Connection refused" in db_check["message"]
    
    @patch.dict(os.environ, {
        "ARBITRAGE_ENV": "paper",
        "READ_ONLY_ENFORCED": "true",
        "POSTGRES_DSN": "postgresql://arbitrage:arbitrage@localhost:5432/arbitrage",
        "REDIS_URL": "redis://localhost:6380/0",
        "UPBIT_ACCESS_KEY": "test_key",
        "UPBIT_SECRET_KEY": "test_secret",
        "BINANCE_API_KEY": "test_key",
        "BINANCE_API_SECRET": "test_secret",
        "TELEGRAM_BOT_TOKEN": "test_token",
        "TELEGRAM_CHAT_ID": "test_id",
    }, clear=True)
    @patch("redis.from_url")
    @patch("psycopg2.connect")
    def test_preflight_realcheck_postgres_fail(self, mock_pg_connect, mock_redis):
        """Real-Check: Postgres 연결 실패 → FAIL"""
        # Mock Redis success
        mock_redis_client = MagicMock()
        mock_redis_client.ping.return_value = True
        mock_redis_client.get.return_value = b"ok"
        mock_redis_client.set.return_value = True
        mock_redis_client.delete.return_value = 1
        mock_redis.return_value = mock_redis_client
        
        # Mock Postgres failure
        mock_pg_connect.side_effect = Exception("Connection refused")
        
        # Real-Check 실행
        checker = LivePreflightChecker(dry_run=False)
        result = checker.run_all_checks()
        
        assert result.is_ready() is False
        assert result.failed >= 1
        
        # Database check가 FAIL
        db_check = [c for c in result.checks if c["name"] == "Database"][0]
        assert db_check["status"] == "FAIL"
        assert "Connection refused" in db_check["message"]
    
    @patch.dict(os.environ, {
        "ARBITRAGE_ENV": "paper",
        "READ_ONLY_ENFORCED": "true",
        "POSTGRES_DSN": "postgresql://arbitrage:arbitrage@localhost:5432/arbitrage",
        "REDIS_URL": "redis://localhost:6380/0",
        "UPBIT_ACCESS_KEY": "test_key",
        "UPBIT_SECRET_KEY": "test_secret",
        "BINANCE_API_KEY": "test_key",
        "BINANCE_API_SECRET": "test_secret",
        "TELEGRAM_BOT_TOKEN": "test_token",
        "TELEGRAM_CHAT_ID": "test_id",
    }, clear=True)
    @patch("redis.from_url")
    @patch("psycopg2.connect")
    def test_preflight_realcheck_exchange_paper_pass(self, mock_pg_connect, mock_redis):
        """Real-Check: Paper 모드 Exchange 검증 → PASS"""
        # Mock Redis + Postgres
        mock_redis_client = MagicMock()
        mock_redis_client.ping.return_value = True
        mock_redis_client.get.return_value = b"ok"
        mock_redis_client.set.return_value = True
        mock_redis_client.delete.return_value = 1
        mock_redis.return_value = mock_redis_client
        
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (1,)
        mock_conn.cursor.return_value = mock_cursor
        mock_pg_connect.return_value = mock_conn
        
        # Real-Check 실행
        checker = LivePreflightChecker(dry_run=False)
        result = checker.run_all_checks()
        
        assert result.is_ready() is True
        
        # Exchange Health check가 PASS
        exchange_check = [c for c in result.checks if c["name"] == "Exchange Health"][0]
        assert exchange_check["status"] == "PASS"
        assert exchange_check["details"]["env"] == "paper"
    
    @patch.dict(os.environ, {
        "ARBITRAGE_ENV": "paper",
        "READ_ONLY_ENFORCED": "true",
        "POSTGRES_DSN": "postgresql://arbitrage:arbitrage@localhost:5432/arbitrage",
        "REDIS_URL": "redis://localhost:6380/0",
        "UPBIT_ACCESS_KEY": "test_key",
        "UPBIT_SECRET_KEY": "test_secret",
        "BINANCE_API_KEY": "test_key",
        "BINANCE_API_SECRET": "test_secret",
        "TELEGRAM_BOT_TOKEN": "test_token",
        "TELEGRAM_CHAT_ID": "test_id",
    }, clear=True)
    def test_preflight_readonly_guard_integration(self):
        """ReadOnlyGuard 통합: READ_ONLY_ENFORCED=true → PASS"""
        checker = LivePreflightChecker(dry_run=True)
        result = checker.run_all_checks()
        
        # READ_ONLY_ENFORCED=true이므로 PASS
        assert result.is_ready() is True
        
        # ReadOnly Guard check가 PASS
        readonly_check = [c for c in result.checks if c["name"] == "ReadOnly Guard"][0]
        assert readonly_check["status"] == "PASS"


class TestPreflightResult:
    """PreflightResult 클래스 테스트"""
    
    def test_add_check_pass(self):
        """add_check: PASS 카운터 증가"""
        result = PreflightResult()
        result.add_check("Test", "PASS", "Success")
        
        assert result.passed == 1
        assert result.failed == 0
        assert len(result.checks) == 1
    
    def test_add_check_fail(self):
        """add_check: FAIL 카운터 증가"""
        result = PreflightResult()
        result.add_check("Test", "FAIL", "Failed")
        
        assert result.passed == 0
        assert result.failed == 1
        assert len(result.checks) == 1
    
    def test_is_ready_pass(self):
        """is_ready: FAIL 0개 → True"""
        result = PreflightResult()
        result.add_check("Test1", "PASS", "Success")
        result.add_check("Test2", "PASS", "Success")
        
        assert result.is_ready() is True
    
    def test_is_ready_fail(self):
        """is_ready: FAIL 1개 이상 → False"""
        result = PreflightResult()
        result.add_check("Test1", "PASS", "Success")
        result.add_check("Test2", "FAIL", "Failed")
        
        assert result.is_ready() is False
    
    def test_to_dict(self):
        """to_dict: 결과를 dict로 변환"""
        result = PreflightResult()
        result.add_check("Test", "PASS", "Success", {"key": "value"})
        
        data = result.to_dict()
        
        assert "summary" in data
        assert "checks" in data
        assert data["summary"]["total_checks"] == 1
        assert data["summary"]["passed"] == 1
        assert data["checks"][0]["name"] == "Test"
