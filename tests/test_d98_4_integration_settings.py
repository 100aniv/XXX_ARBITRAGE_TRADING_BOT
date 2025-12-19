# -*- coding: utf-8 -*-
"""
D98-4: Live Key Guard 통합 테스트 (Settings)
============================================

Settings.from_env()와 LiveKeyGuard의 통합 테스트.

Test Coverage:
--------------
1. Settings.from_env() 호출 시 LiveKeyGuard 작동 확인
2. 다양한 환경 변수 조합 시나리오
3. 실제 키 로딩 흐름 검증

Integration Points:
-------------------
- arbitrage.config.settings.Settings.from_env()
- arbitrage.config.live_key_guard.validate_live_keys()
"""

import os
import pytest
from unittest.mock import patch, Mock

from arbitrage.config.settings import Settings, RuntimeEnv
from arbitrage.config.live_key_guard import LiveKeyError


class TestSettingsIntegrationWithLiveKeyGuard:
    """Settings.from_env()와 LiveKeyGuard 통합 테스트"""
    
    @patch.dict(os.environ, {
        "ARBITRAGE_ENV": "paper",
        "LIVE_ENABLED": "false",
        "UPBIT_ACCESS_KEY": "test_upbit_key",
        "UPBIT_SECRET_KEY": "test_upbit_secret",
        "BINANCE_API_KEY": "mock_binance_key",
        "BINANCE_API_SECRET": "mock_binance_secret",
        "TELEGRAM_BOT_TOKEN": "test_telegram_token",
        "TELEGRAM_CHAT_ID": "test_chat_id",
    }, clear=True)
    def test_paper_mode_with_test_keys_loads_successfully(self):
        """Paper 모드 + 테스트 키 → Settings 로딩 성공"""
        settings = Settings.from_env()
        
        assert settings.env == RuntimeEnv.PAPER
        assert settings.upbit_access_key == "test_upbit_key"
        assert settings.binance_api_key == "mock_binance_key"
    
    @patch.dict(os.environ, {
        "ARBITRAGE_ENV": "paper",
        "LIVE_ENABLED": "false",
        "UPBIT_ACCESS_KEY": "a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6",  # LIVE 키 패턴
        "UPBIT_SECRET_KEY": "x1y2z3a4b5c6d7e8f9g0h1i2j3k4l5m6",
    }, clear=True)
    def test_paper_mode_with_live_key_blocks_loading(self):
        """Paper 모드 + LIVE 키 → Settings 로딩 차단"""
        with pytest.raises(LiveKeyError) as exc_info:
            Settings.from_env()
        
        assert "LIVE UPBIT_ACCESS_KEY 감지" in str(exc_info.value)
        assert "paper" in str(exc_info.value).lower()
    
    @patch.dict(os.environ, {
        "ARBITRAGE_ENV": "local_dev",
        "LIVE_ENABLED": "false",
        "BINANCE_API_KEY": "realkey123abc456def789ghi012jkl",  # LIVE 키 패턴
        "BINANCE_API_SECRET": "secret456xyz789abc012def345ghi",
    }, clear=True)
    def test_local_dev_with_live_key_blocks_loading(self):
        """Local_dev 모드 + LIVE 키 → Settings 로딩 차단"""
        with pytest.raises(LiveKeyError) as exc_info:
            Settings.from_env()
        
        assert "LIVE BINANCE_API_KEY 감지" in str(exc_info.value)
        assert "local_dev" in str(exc_info.value).lower()
    
    @patch.dict(os.environ, {
        "ARBITRAGE_ENV": "live",
        "LIVE_ENABLED": "true",
        "UPBIT_ACCESS_KEY": "a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6",  # LIVE 키
        "UPBIT_SECRET_KEY": "x1y2z3a4b5c6d7e8f9g0h1i2j3k4l5m6",
        "BINANCE_API_KEY": "realkey123abc456def789ghi012jkl",
        "BINANCE_API_SECRET": "secret456xyz789abc012def345ghi",
        "TELEGRAM_BOT_TOKEN": "live_telegram_token",
        "TELEGRAM_CHAT_ID": "live_chat_id",
    }, clear=True)
    def test_live_mode_with_live_enabled_allows_loading(self):
        """LIVE 모드 + LIVE_ENABLED=true → Settings 로딩 허용"""
        settings = Settings.from_env()
        
        assert settings.env == RuntimeEnv.LIVE
        assert settings.upbit_access_key == "a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6"
        assert settings.binance_api_key == "realkey123abc456def789ghi012jkl"
    
    @patch.dict(os.environ, {
        "ARBITRAGE_ENV": "paper",
        "LIVE_ENABLED": "true",  # 환경 불일치
        "UPBIT_ACCESS_KEY": "test_key",
        "TELEGRAM_BOT_TOKEN": "test_telegram_token",
        "TELEGRAM_CHAT_ID": "test_chat_id",
    }, clear=True)
    def test_live_enabled_true_but_env_paper_blocks(self):
        """LIVE_ENABLED=true 이지만 env=paper → Settings 로딩 차단"""
        with pytest.raises(LiveKeyError) as exc_info:
            Settings.from_env()
        
        assert "환경 불일치" in str(exc_info.value)
        assert "LIVE_ENABLED=true" in str(exc_info.value)
        assert "paper" in str(exc_info.value).lower()
    
    @patch.dict(os.environ, {
        "ARBITRAGE_ENV": "local_dev",
        "LIVE_ENABLED": "false",
        # 키 없음 (Mock 모드)
        "TELEGRAM_BOT_TOKEN": "test_telegram_token",
        "TELEGRAM_CHAT_ID": "test_chat_id",
    }, clear=True)
    def test_local_dev_with_no_keys_loads_successfully(self):
        """Local_dev 모드 + 키 없음 (Mock) → Settings 로딩 성공"""
        settings = Settings.from_env()
        
        assert settings.env == RuntimeEnv.LOCAL_DEV
        assert settings.upbit_access_key is None
        assert settings.binance_api_key is None
    
    @patch.dict(os.environ, {
        "ARBITRAGE_ENV": "paper",
        "LIVE_ENABLED": "false",
        "UPBIT_ACCESS_KEY": "your_upbit_access_key_here",  # .env.example 패턴
        "UPBIT_SECRET_KEY": "your_upbit_secret_key_here",
        "BINANCE_API_KEY": "your_binance_api_key_here",
        "BINANCE_API_SECRET": "your_binance_api_secret_here",
        "TELEGRAM_BOT_TOKEN": "test_telegram_token",
        "TELEGRAM_CHAT_ID": "test_chat_id",
    }, clear=True)
    def test_paper_mode_with_example_keys_loads_successfully(self):
        """Paper 모드 + .env.example 키 → Settings 로딩 성공"""
        settings = Settings.from_env()
        
        assert settings.env == RuntimeEnv.PAPER
        assert settings.upbit_access_key == "your_upbit_access_key_here"


class TestAccidentalKeyLeakScenarios:
    """실수로 LIVE 키가 노출되는 시나리오 테스트"""
    
    @patch.dict(os.environ, {
        "ARBITRAGE_ENV": "paper",
        "LIVE_ENABLED": "false",
        "UPBIT_ACCESS_KEY": "test_safe_key",
        "UPBIT_SECRET_KEY": "LiveProductionSecret123Abc",  # 하나만 LIVE 키
        "TELEGRAM_BOT_TOKEN": "test_telegram_token",
        "TELEGRAM_CHAT_ID": "test_chat_id",
    }, clear=True)
    def test_one_live_key_among_test_keys_blocked(self):
        """테스트 키 중 하나라도 LIVE 키면 차단"""
        with pytest.raises(LiveKeyError) as exc_info:
            Settings.from_env()
        
        assert "LIVE UPBIT_SECRET_KEY 감지" in str(exc_info.value)
    
    @patch.dict(os.environ, {
        "ARBITRAGE_ENV": "paper",
        "LIVE_ENABLED": "false",
        "UPBIT_ACCESS_KEY": "test_key",
        "UPBIT_SECRET_KEY": "test_secret",
        "BINANCE_API_KEY": "ProductionApiKey12345AbcDefGhi",  # LIVE 키
        "BINANCE_API_SECRET": "test_binance_secret",
        "TELEGRAM_BOT_TOKEN": "test_telegram_token",
        "TELEGRAM_CHAT_ID": "test_chat_id",
    }, clear=True)
    def test_mixed_test_and_live_keys_blocked(self):
        """Upbit는 테스트, Binance는 LIVE → 차단"""
        with pytest.raises(LiveKeyError) as exc_info:
            Settings.from_env()
        
        assert "LIVE BINANCE_API_KEY 감지" in str(exc_info.value)


class TestCIPipelineScenarios:
    """CI/CD 파이프라인 시나리오 테스트"""
    
    @patch.dict(os.environ, {
        "ARBITRAGE_ENV": "paper",
        "LIVE_ENABLED": "false",
        # GitHub Actions에서 실수로 LIVE secrets 주입
        "UPBIT_ACCESS_KEY": "GithubActionsLiveKey123456789",
        "UPBIT_SECRET_KEY": "GithubSecretsLiveSecret987654",
        "TELEGRAM_BOT_TOKEN": "test_telegram_token",
        "TELEGRAM_CHAT_ID": "test_chat_id",
    }, clear=True)
    def test_ci_with_wrong_secrets_blocked(self):
        """CI에서 잘못된 secrets 주입 시 차단"""
        with pytest.raises(LiveKeyError):
            Settings.from_env()
    
    @patch.dict(os.environ, {
        "ARBITRAGE_ENV": "paper",
        "LIVE_ENABLED": "false",
        # CI에서 올바른 test secrets 주입
        "UPBIT_ACCESS_KEY": "ci_test_upbit_key",
        "UPBIT_SECRET_KEY": "ci_test_upbit_secret",
        "BINANCE_API_KEY": "ci_mock_binance_key",
        "BINANCE_API_SECRET": "ci_mock_binance_secret",
        "TELEGRAM_BOT_TOKEN": "ci_test_telegram_token",
        "TELEGRAM_CHAT_ID": "ci_test_chat_id",
    }, clear=True)
    def test_ci_with_correct_test_secrets_allowed(self):
        """CI에서 올바른 테스트 secrets 주입 시 허용"""
        settings = Settings.from_env()
        assert settings.env == RuntimeEnv.PAPER


class TestSecretsProviderIntegration:
    """Secrets Provider와 LiveKeyGuard 통합 테스트"""
    
    @patch.dict(os.environ, {
        "ARBITRAGE_ENV": "paper",
        "LIVE_ENABLED": "false",
        "TELEGRAM_BOT_TOKEN": "test_telegram_token",
        "TELEGRAM_CHAT_ID": "test_chat_id",
    }, clear=True)
    def test_secrets_provider_with_live_key_blocked(self):
        """Secrets Provider가 LIVE 키 반환 시 차단"""
        # Mock secrets provider
        mock_provider = Mock()
        mock_provider.get_secret.side_effect = lambda key, default=None: {
            "UPBIT_ACCESS_KEY": "ProviderLiveKey123456789Abc",
            "UPBIT_SECRET_KEY": "ProviderLiveSecret987654321",
        }.get(key, default)
        
        with pytest.raises(LiveKeyError) as exc_info:
            Settings.from_env(secrets_provider=mock_provider)
        
        assert "LIVE UPBIT_ACCESS_KEY 감지" in str(exc_info.value)
    
    @patch.dict(os.environ, {
        "ARBITRAGE_ENV": "paper",
        "LIVE_ENABLED": "false",
        "TELEGRAM_BOT_TOKEN": "test_telegram_token",
        "TELEGRAM_CHAT_ID": "test_chat_id",
    }, clear=True)
    def test_secrets_provider_with_test_key_allowed(self):
        """Secrets Provider가 테스트 키 반환 시 허용"""
        mock_provider = Mock()
        mock_provider.get_secret.side_effect = lambda key, default=None: {
            "UPBIT_ACCESS_KEY": "test_provider_upbit_key",
            "UPBIT_SECRET_KEY": "test_provider_upbit_secret",
        }.get(key, default)
        
        settings = Settings.from_env(secrets_provider=mock_provider)
        assert settings.upbit_access_key == "test_provider_upbit_key"


class TestLiveKeyGuardLogging:
    """LiveKeyGuard 로깅 동작 테스트"""
    
    @patch.dict(os.environ, {
        "ARBITRAGE_ENV": "live",
        "LIVE_ENABLED": "true",
        "UPBIT_ACCESS_KEY": "LiveKey123456789AbcDef",
        "UPBIT_SECRET_KEY": "LiveSecret987654321XyzAbc",
        "TELEGRAM_BOT_TOKEN": "live_telegram_token",
        "TELEGRAM_CHAT_ID": "live_chat_id",
    }, clear=True)
    def test_live_mode_logs_warning(self, caplog):
        """LIVE 모드 활성화 시 로그 출력 확인"""
        with caplog.at_level("INFO", logger="arbitrage.config.live_key_guard"):
            Settings.from_env()
        
        # LIVE 모드 활성화 로그 확인
        log_messages = [record.message for record in caplog.records]
        assert any("LIVE 모드 활성화" in msg for msg in log_messages)
    
    @patch.dict(os.environ, {
        "ARBITRAGE_ENV": "paper",
        "LIVE_ENABLED": "false",
        "UPBIT_ACCESS_KEY": "test_key",
        "UPBIT_SECRET_KEY": "test_secret",
        "TELEGRAM_BOT_TOKEN": "test_telegram_token",
        "TELEGRAM_CHAT_ID": "test_chat_id",
    }, clear=True)
    def test_paper_mode_logs_validation_pass(self, caplog):
        """Paper 모드 검증 통과 시 로그 출력 확인"""
        with caplog.at_level("INFO", logger="arbitrage.config.live_key_guard"):
            Settings.from_env()
        
        log_messages = [record.message for record in caplog.records]
        assert any("키 검증 통과" in msg for msg in log_messages)


class TestBackwardCompatibility:
    """기존 코드와의 호환성 테스트"""
    
    @patch.dict(os.environ, {
        "ARBITRAGE_ENV": "local_dev",
        "LIVE_ENABLED": "false",
        # 기존 코드는 키 없이도 작동해야 함
        "TELEGRAM_BOT_TOKEN": "test_telegram_token",
        "TELEGRAM_CHAT_ID": "test_chat_id",
    }, clear=True)
    def test_legacy_code_without_keys_still_works(self):
        """기존 코드 (키 없음) 여전히 작동 확인"""
        settings = Settings.from_env()
        assert settings.env == RuntimeEnv.LOCAL_DEV
    
    @patch.dict(os.environ, {
        "ARBITRAGE_ENV": "paper",
        "LIVE_ENABLED": "false",
        "UPBIT_ACCESS_KEY": "dummy_key",
        "UPBIT_SECRET_KEY": "dummy_secret",
        "BINANCE_API_KEY": "placeholder_key",
        "BINANCE_API_SECRET": "placeholder_secret",
        "TELEGRAM_BOT_TOKEN": "test_telegram_token",
        "TELEGRAM_CHAT_ID": "test_chat_id",
    }, clear=True)
    def test_legacy_dummy_keys_still_allowed(self):
        """기존 dummy 키 여전히 허용 확인"""
        settings = Settings.from_env()
        assert settings.upbit_access_key == "dummy_key"
        assert settings.binance_api_key == "placeholder_key"


class TestFailClosedPrinciple:
    """Fail-Closed 원칙 테스트"""
    
    @patch.dict(os.environ, {
        "ARBITRAGE_ENV": "paper",
        # LIVE_ENABLED 없음 (기본값 false)
        "UPBIT_ACCESS_KEY": "AmbiguousKey123",
        "UPBIT_SECRET_KEY": "AmbiguousSecret456",
        "TELEGRAM_BOT_TOKEN": "test_telegram_token",
        "TELEGRAM_CHAT_ID": "test_chat_id",
    }, clear=True)
    def test_ambiguous_key_allowed_if_short(self):
        """애매한 키도 짧으면 허용 (20자 미만)"""
        settings = Settings.from_env()
        assert settings.upbit_access_key == "AmbiguousKey123"
    
    @patch.dict(os.environ, {
        "ARBITRAGE_ENV": "paper",
        "UPBIT_ACCESS_KEY": "AmbiguousKey1234567890",  # 20자 이상
    }, clear=True)
    def test_ambiguous_long_key_blocked_fail_closed(self):
        """애매한 키이지만 길면 차단 (Fail-Closed)"""
        with pytest.raises(LiveKeyError):
            Settings.from_env()
