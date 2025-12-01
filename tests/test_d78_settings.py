# -*- coding: utf-8 -*-
"""
D78-0: Settings & Secrets Layer Tests

Test coverage:
1. Settings loading from environment
2. Environment-specific validation
3. DSN/URL generation
4. Override mechanism for testing
5. Singleton behavior
"""

import os
import pytest
from arbitrage.config.settings import (
    Settings,
    RuntimeEnv,
    get_settings,
    reload_settings,
    get_app_env,
)


class TestSettingsBasic:
    """Basic settings functionality"""
    
    def test_settings_creation_local_dev(self):
        """Test settings creation with local_dev environment"""
        # Save original env
        orig_env = os.environ.get("ARBITRAGE_ENV")
        
        try:
            os.environ["ARBITRAGE_ENV"] = "local_dev"
            settings = Settings.from_env()
            
            assert settings.env == RuntimeEnv.LOCAL_DEV
            assert settings.postgres_host == "localhost"
            assert settings.redis_host == "localhost"
        
        finally:
            # Restore
            if orig_env:
                os.environ["ARBITRAGE_ENV"] = orig_env
            else:
                os.environ.pop("ARBITRAGE_ENV", None)
    
    def test_settings_with_overrides(self):
        """Test settings override mechanism"""
        settings = Settings.from_env(overrides={
            "env": RuntimeEnv.LOCAL_DEV,  # Use LOCAL_DEV to avoid validation errors
            "upbit_access_key": "test_key",
        })
        
        assert settings.env == RuntimeEnv.LOCAL_DEV
        assert settings.upbit_access_key == "test_key"
    
    def test_postgres_dsn_generation(self):
        """Test PostgreSQL DSN generation"""
        settings = Settings.from_env(overrides={
            "postgres_host": "dbhost",
            "postgres_port": 5432,
            "postgres_db": "testdb",
            "postgres_user": "testuser",
            "postgres_password": "testpass",
        })
        
        dsn = settings.get_postgres_dsn()
        assert "postgresql://" in dsn
        assert "testuser:testpass" in dsn
        assert "dbhost:5432" in dsn
        assert "testdb" in dsn
    
    def test_postgres_dsn_direct(self):
        """Test PostgreSQL DSN when provided directly"""
        direct_dsn = "postgresql://user:pass@host:5432/db"
        settings = Settings.from_env(overrides={
            "postgres_dsn": direct_dsn,
        })
        
        assert settings.get_postgres_dsn() == direct_dsn
    
    def test_redis_url_generation(self):
        """Test Redis URL generation"""
        settings = Settings.from_env(overrides={
            "redis_host": "redishost",
            "redis_port": 6379,
            "redis_db": 1,
        })
        
        url = settings.get_redis_url()
        assert url == "redis://redishost:6379/1"
    
    def test_redis_url_direct(self):
        """Test Redis URL when provided directly"""
        direct_url = "redis://myhost:6380/2"
        settings = Settings.from_env(overrides={
            "redis_url": direct_url,
        })
        
        assert settings.get_redis_url() == direct_url


class TestEnvironmentValidation:
    """Environment-specific validation tests"""
    
    def test_local_dev_allows_none(self):
        """Test local_dev allows None credentials (warnings only)"""
        # This should not raise, just print warnings
        settings = Settings.from_env(overrides={
            "env": RuntimeEnv.LOCAL_DEV,
            "upbit_access_key": None,
            "binance_api_key": None,
            "telegram_bot_token": None,
        })
        
        # Should complete without exception
        assert settings.env == RuntimeEnv.LOCAL_DEV
    
    def test_paper_requires_credentials(self):
        """Test paper environment requires exchange + telegram + db"""
        # Missing exchange keys
        with pytest.raises(ValueError) as exc_info:
            Settings.from_env(overrides={
                "env": RuntimeEnv.PAPER,
                "upbit_access_key": None,
                "binance_api_key": None,
                "telegram_bot_token": "test_token",
                "telegram_default_chat_id": "test_chat",
            })
        
        assert "exchange" in str(exc_info.value).lower()
    
    def test_paper_requires_telegram(self):
        """Test paper environment requires Telegram"""
        with pytest.raises(ValueError) as exc_info:
            Settings.from_env(overrides={
                "env": RuntimeEnv.PAPER,
                "upbit_access_key": "test_key",
                "upbit_secret_key": "test_secret",
                "telegram_bot_token": None,
            })
        
        assert "telegram" in str(exc_info.value).lower()
    
    def test_paper_with_all_required(self):
        """Test paper environment with all required credentials"""
        # Should not raise
        settings = Settings.from_env(overrides={
            "env": RuntimeEnv.PAPER,
            "upbit_access_key": "test_key",
            "upbit_secret_key": "test_secret",
            "telegram_bot_token": "test_token",
            "telegram_default_chat_id": "test_chat",
            "postgres_host": "localhost",
        })
        
        assert settings.env == RuntimeEnv.PAPER
        assert settings.upbit_access_key == "test_key"


class TestSingleton:
    """Test singleton behavior"""
    
    def test_get_settings_singleton(self):
        """Test get_settings returns same instance"""
        # Clear singleton first
        import arbitrage.config.settings as settings_module
        settings_module._settings_instance = None
        
        settings1 = get_settings()
        settings2 = get_settings()
        
        # Should be same instance
        assert settings1 is settings2
    
    def test_reload_settings(self):
        """Test reload_settings forces new instance"""
        # Clear singleton first
        import arbitrage.config.settings as settings_module
        settings_module._settings_instance = None
        
        settings1 = get_settings()
        settings2 = reload_settings()
        
        # Should be different instances
        assert settings1 is not settings2
    
    def test_get_settings_with_overrides_not_cached(self):
        """Test get_settings with overrides creates new instance"""
        # Clear singleton first
        import arbitrage.config.settings as settings_module
        settings_module._settings_instance = None
        
        settings1 = get_settings()
        settings2 = get_settings(overrides={
            "env": RuntimeEnv.LOCAL_DEV,  # Use LOCAL_DEV to avoid validation errors
            "upbit_access_key": "test_override",
        })
        
        # Overrides should create new instance
        assert settings1 is not settings2
        assert settings2.upbit_access_key == "test_override"


class TestToDict:
    """Test settings serialization"""
    
    def test_to_dict(self):
        """Test settings.to_dict() for logging"""
        settings = Settings.from_env(overrides={
            "env": RuntimeEnv.LOCAL_DEV,
            "upbit_access_key": "test_key",
            "telegram_bot_token": "test_token",
            "telegram_default_chat_id": "test_chat",
        })
        
        d = settings.to_dict()
        
        assert d["env"] == "local_dev"
        assert d["upbit_configured"] is True
        assert d["telegram_configured"] is True
        # Should not expose actual credentials
        assert "test_key" not in str(d)
        assert "test_token" not in str(d)


class TestBackwardCompatibility:
    """Test backward compatibility with APP_ENV"""
    
    def test_get_app_env_mapping(self):
        """Test get_app_env() maps ARBITRAGE_ENV to APP_ENV"""
        # Clear singleton
        import arbitrage.config.settings as settings_module
        
        # Test local_dev → development
        settings_module._settings_instance = None
        settings = get_settings(overrides={"env": RuntimeEnv.LOCAL_DEV})
        app_env = get_app_env()
        assert app_env == "development"
        
        # Test paper → staging (provide required credentials)
        settings_module._settings_instance = None
        settings = get_settings(overrides={
            "env": RuntimeEnv.PAPER,
            "upbit_access_key": "test",
            "upbit_secret_key": "test",
            "telegram_bot_token": "test",
            "telegram_default_chat_id": "test",
        })
        app_env = get_app_env()
        assert app_env == "staging"
        
        # Test live → production (provide required credentials)
        settings_module._settings_instance = None
        settings = get_settings(overrides={
            "env": RuntimeEnv.LIVE,
            "upbit_access_key": "test",
            "upbit_secret_key": "test",
            "telegram_bot_token": "test",
            "telegram_default_chat_id": "test",
        })
        app_env = get_app_env()
        assert app_env == "production"
        
        # Clear singleton
        settings_module._settings_instance = None


class TestEnvironmentVariableLoading:
    """Test loading from environment variables"""
    
    def test_load_from_env_vars(self):
        """Test loading credentials from environment variables"""
        # Save originals
        orig_vars = {
            "ARBITRAGE_ENV": os.environ.get("ARBITRAGE_ENV"),
            "UPBIT_ACCESS_KEY": os.environ.get("UPBIT_ACCESS_KEY"),
            "TELEGRAM_BOT_TOKEN": os.environ.get("TELEGRAM_BOT_TOKEN"),
        }
        
        try:
            # Set test env vars
            os.environ["ARBITRAGE_ENV"] = "local_dev"
            os.environ["UPBIT_ACCESS_KEY"] = "env_test_key"
            os.environ["TELEGRAM_BOT_TOKEN"] = "env_test_token"
            
            # Clear singleton to force reload
            import arbitrage.config.settings as settings_module
            settings_module._settings_instance = None
            
            settings = get_settings()
            
            assert settings.env == RuntimeEnv.LOCAL_DEV
            assert settings.upbit_access_key == "env_test_key"
            assert settings.telegram_bot_token == "env_test_token"
        
        finally:
            # Restore
            for key, value in orig_vars.items():
                if value is not None:
                    os.environ[key] = value
                else:
                    os.environ.pop(key, None)
            
            # Clear singleton
            import arbitrage.config.settings as settings_module
            settings_module._settings_instance = None
