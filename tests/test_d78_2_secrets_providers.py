# -*- coding: utf-8 -*-
"""
D78-2: Secrets Providers - Tests

SecretsProvider 인터페이스 및 구현체 테스트.
"""

import pytest
import os
import json
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from arbitrage.config.secrets_providers import (
    SecretsProviderBase,
    SecretNotFoundError,
    EnvSecretsProvider,
    LocalFallbackProvider,
    VaultSecretsProvider,
    KMSSecretsProvider,
)


class TestEnvSecretsProvider:
    """EnvSecretsProvider 테스트"""
    
    def test_get_secret_from_env(self, monkeypatch):
        """환경변수에서 secret 조회"""
        monkeypatch.setenv("TEST_SECRET", "test_value")
        
        provider = EnvSecretsProvider()
        value = provider.get_secret("TEST_SECRET")
        
        assert value == "test_value"
    
    def test_get_secret_with_default(self):
        """기본값 사용"""
        provider = EnvSecretsProvider()
        value = provider.get_secret("NONEXISTENT_SECRET", default="default_value")
        
        assert value == "default_value"
    
    def test_get_secret_not_found(self):
        """Secret이 없을 때 예외 발생"""
        provider = EnvSecretsProvider()
        
        with pytest.raises(SecretNotFoundError):
            provider.get_secret("NONEXISTENT_SECRET")
    
    def test_set_secret(self, monkeypatch):
        """환경변수 설정 (runtime)"""
        provider = EnvSecretsProvider()
        provider.set_secret("TEST_NEW_SECRET", "new_value")
        
        # Runtime 환경변수 확인
        assert os.getenv("TEST_NEW_SECRET") == "new_value"
    
    def test_list_secrets(self, monkeypatch):
        """환경변수 목록 조회"""
        monkeypatch.setenv("TEST_1", "value1")
        monkeypatch.setenv("TEST_2", "value2")
        
        provider = EnvSecretsProvider()
        secrets = provider.list_secrets()
        
        assert "TEST_1" in secrets
        assert "TEST_2" in secrets
    
    def test_health(self):
        """Provider 상태 확인"""
        provider = EnvSecretsProvider()
        health = provider.health()
        
        assert health["status"] == "healthy"
        assert health["provider_type"] == "env"
        assert "env_count" in health["details"]


class TestLocalFallbackProvider:
    """LocalFallbackProvider 테스트"""
    
    def test_get_secret_from_file(self, tmp_path):
        """파일에서 secret 조회"""
        secrets_file = tmp_path / ".secrets.local.json"
        secrets_data = {"TEST_KEY": "test_value"}
        secrets_file.write_text(json.dumps(secrets_data))
        
        provider = LocalFallbackProvider(secrets_file=secrets_file)
        value = provider.get_secret("TEST_KEY")
        
        assert value == "test_value"
    
    def test_get_secret_with_default(self, tmp_path):
        """기본값 사용"""
        secrets_file = tmp_path / ".secrets.local.json"
        
        provider = LocalFallbackProvider(secrets_file=secrets_file)
        value = provider.get_secret("NONEXISTENT", default="default")
        
        assert value == "default"
    
    def test_get_secret_not_found(self, tmp_path):
        """Secret이 없을 때 예외 발생"""
        secrets_file = tmp_path / ".secrets.local.json"
        
        provider = LocalFallbackProvider(secrets_file=secrets_file)
        
        with pytest.raises(SecretNotFoundError):
            provider.get_secret("NONEXISTENT")
    
    def test_set_secret(self, tmp_path):
        """파일에 secret 저장"""
        secrets_file = tmp_path / ".secrets.local.json"
        
        provider = LocalFallbackProvider(secrets_file=secrets_file)
        provider.set_secret("NEW_KEY", "new_value")
        
        # 파일 확인
        assert secrets_file.exists()
        data = json.loads(secrets_file.read_text())
        assert data["NEW_KEY"] == "new_value"
    
    def test_list_secrets(self, tmp_path):
        """Secret 목록 조회"""
        secrets_file = tmp_path / ".secrets.local.json"
        secrets_data = {"KEY1": "value1", "KEY2": "value2"}
        secrets_file.write_text(json.dumps(secrets_data))
        
        provider = LocalFallbackProvider(secrets_file=secrets_file)
        secrets = provider.list_secrets()
        
        assert set(secrets) == {"KEY1", "KEY2"}
    
    def test_health(self, tmp_path):
        """Provider 상태 확인"""
        secrets_file = tmp_path / ".secrets.local.json"
        secrets_file.write_text("{}")
        
        provider = LocalFallbackProvider(secrets_file=secrets_file)
        health = provider.health()
        
        assert health["status"] == "healthy"
        assert health["provider_type"] == "local_fallback"
        assert health["details"]["file_exists"] is True
    
    def test_health_file_not_exists(self, tmp_path):
        """파일이 없을 때 degraded 상태"""
        secrets_file = tmp_path / ".secrets.local.json"
        
        provider = LocalFallbackProvider(secrets_file=secrets_file)
        health = provider.health()
        
        assert health["status"] == "degraded"
        assert health["details"]["file_exists"] is False


@pytest.mark.skip(reason="Vault/KMS tests require optional dependencies (hvac, boto3)")
class TestVaultSecretsProvider:
    """VaultSecretsProvider 테스트 (skipped - optional dependencies)"""
    pass


@pytest.mark.skip(reason="Vault/KMS tests require optional dependencies (hvac, boto3)")
class TestKMSSecretsProvider:
    """KMSSecretsProvider 테스트 (skipped - optional dependencies)"""
    pass


class TestSettingsWithSecretsProvider:
    """Settings + SecretsProvider 통합 테스트"""
    
    def test_settings_uses_env_provider_by_default(self, monkeypatch):
        """기본값으로 EnvSecretsProvider 사용"""
        monkeypatch.setenv("ARBITRAGE_ENV", "local_dev")
        monkeypatch.setenv("UPBIT_ACCESS_KEY", "test_key")
        
        from arbitrage.config.settings import Settings
        
        settings = Settings.from_env()
        
        assert settings.upbit_access_key == "test_key"
        assert settings.secrets_provider is not None
        assert settings.secrets_provider.__class__.__name__ == "EnvSecretsProvider"
    
    def test_settings_with_custom_provider(self, tmp_path, monkeypatch):
        """커스텀 SecretsProvider 사용"""
        # Local fallback provider 생성
        secrets_file = tmp_path / ".secrets.local.json"
        secrets_data = {
            "ARBITRAGE_ENV": "local_dev",
            "UPBIT_ACCESS_KEY": "custom_key",
            "UPBIT_SECRET_KEY": "custom_secret",
        }
        secrets_file.write_text(json.dumps(secrets_data))
        
        provider = LocalFallbackProvider(secrets_file=secrets_file)
        
        from arbitrage.config.settings import Settings
        
        settings = Settings.from_env(secrets_provider=provider)
        
        assert settings.upbit_access_key == "custom_key"
        assert settings.upbit_secret_key == "custom_secret"
    
    def test_settings_backward_compatible(self, monkeypatch):
        """기존 .env 파일 방식과 호환"""
        monkeypatch.setenv("ARBITRAGE_ENV", "local_dev")
        monkeypatch.setenv("BINANCE_API_KEY", "legacy_key")
        
        from arbitrage.config.settings import Settings
        
        # secrets_provider 없이 호출
        settings = Settings.from_env()
        
        # 기존 방식대로 동작
        assert settings.binance_api_key == "legacy_key"
