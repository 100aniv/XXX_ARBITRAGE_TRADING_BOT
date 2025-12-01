# -*- coding: utf-8 -*-
"""
D78-0: Authentication & Secrets Layer

중앙화된 설정 및 인증 정보 관리 모듈

Codebase Scan Summary:
=====================
이 모듈은 다음 위치에서 사용되던 환경변수/credentials를 중앙화합니다:

1. **Telegram** (arbitrage/alerting/notifiers/telegram_notifier.py):
   - TELEGRAM_BOT_TOKEN
   - TELEGRAM_CHAT_ID

2. **Redis** (scripts/, arbitrage/monitoring.py, healthcheck.py):
   - REDIS_HOST
   - REDIS_PORT
   - REDIS_DB

3. **PostgreSQL** (scripts/, tests/):
   - POSTGRES_HOST, POSTGRES_PORT, POSTGRES_DB
   - POSTGRES_USER, POSTGRES_PASSWORD
   - DATABASE_URL (DSN 형식)

4. **Upbit/Binance Exchange** (arbitrage/exchange/):
   - UPBIT_ACCESS_KEY, UPBIT_SECRET_KEY
   - BINANCE_API_KEY, BINANCE_API_SECRET
   - Exchange adapters는 이미 생성자 파라미터로 받음

5. **Email/Slack** (arbitrage/alerting/notifiers/):
   - SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD
   - SLACK_WEBHOOK_URL

6. **Environment** (다수 파일):
   - APP_ENV, ARBITRAGE_ENV, ENV → 통합: ARBITRAGE_ENV

Environment Model:
==================
- local_dev: 로컬 개발 (mock, test chats, local DB 허용)
- paper: 실제 시장 데이터 + PAPER 트레이딩 (실제 API keys 필요)
- live: 실제 거래 (향후, 현재는 구조만 정의)

Usage:
======
```python
from arbitrage.config.settings import get_settings

settings = get_settings()
print(f"Environment: {settings.env}")
print(f"Telegram Token: {settings.telegram_bot_token}")
```

For tests (with overrides):
```python
settings = get_settings(overrides={"env": "local_dev"})
```
"""

import os
from enum import Enum
from typing import Optional, Dict, Any, TYPE_CHECKING
from dataclasses import dataclass, field

if TYPE_CHECKING:
    from arbitrage.config.secrets_providers.base import SecretsProviderBase


class RuntimeEnv(str, Enum):
    """Runtime environment"""
    LOCAL_DEV = "local_dev"
    PAPER = "paper"
    LIVE = "live"


@dataclass
class Settings:
    """
    Central settings & secrets configuration
    
    Environment Variable Naming:
    - ARBITRAGE_ENV: Environment selection (local_dev|paper|live)
    - UPBIT_*: Upbit API credentials
    - BINANCE_*: Binance API credentials
    - TELEGRAM_*: Telegram bot configuration
    - POSTGRES_*: PostgreSQL connection
    - REDIS_*: Redis connection
    - SMTP_*: Email configuration
    - SLACK_*: Slack webhook
    """
    
    # Environment
    env: RuntimeEnv = RuntimeEnv.LOCAL_DEV
    
    # Upbit
    upbit_access_key: Optional[str] = None
    upbit_secret_key: Optional[str] = None
    
    # Binance
    binance_api_key: Optional[str] = None
    binance_api_secret: Optional[str] = None
    
    # Telegram
    telegram_bot_token: Optional[str] = None
    telegram_default_chat_id: Optional[str] = None
    
    # PostgreSQL
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "arbitrage"
    postgres_user: str = "arbitrage"
    postgres_password: str = "arbitrage"
    postgres_dsn: Optional[str] = None  # Full DSN (우선순위 높음)
    
    # Redis
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    redis_url: Optional[str] = None  # Full URL (우선순위 높음)
    
    # Email (SMTP)
    smtp_host: Optional[str] = None
    smtp_port: int = 587
    smtp_user: Optional[str] = None
    smtp_password: Optional[str] = None
    smtp_use_tls: bool = True
    
    # Slack
    slack_webhook_url: Optional[str] = None
    
    # Monitoring
    prometheus_enabled: bool = True
    prometheus_port: int = 9100
    grafana_enabled: bool = True
    
    # Misc
    app_env: Optional[str] = None  # Backward compatibility (APP_ENV)
    
    # D78-2: Secrets Provider (optional)
    secrets_provider: Optional["SecretsProviderBase"] = field(default=None, repr=False)
    
    @classmethod
    def from_env(
        cls,
        overrides: Optional[Dict[str, Any]] = None,
        secrets_provider: Optional["SecretsProviderBase"] = None,
    ) -> "Settings":
        """
        Load settings from environment variables
        
        Args:
            overrides: Optional dict to override specific settings (for testing)
            secrets_provider: Optional SecretsProvider (D78-2)
                            If None, uses environment variables (backward compatible)
        
        Returns:
            Settings instance
        """
        # D78-2: Auto-select secrets provider if not provided
        if secrets_provider is None:
            # Default: EnvSecretsProvider (backward compatible)
            from arbitrage.config.secrets_providers import EnvSecretsProvider
            secrets_provider = EnvSecretsProvider()
        
        # Helper function to get value from provider or env
        def get_value(key: str, default: Optional[str] = None) -> Optional[str]:
            try:
                return secrets_provider.get_secret(key, default=default)
            except Exception:
                # Fallback to environment variable
                return os.getenv(key, default)
        
        # Environment
        env_str = get_value("ARBITRAGE_ENV", "local_dev").lower()
        try:
            env = RuntimeEnv(env_str)
        except ValueError:
            print(f"Warning: Invalid ARBITRAGE_ENV '{env_str}', defaulting to local_dev")
            env = RuntimeEnv.LOCAL_DEV
        
        # Upbit (use secrets provider)
        upbit_access_key = get_value("UPBIT_ACCESS_KEY")
        upbit_secret_key = get_value("UPBIT_SECRET_KEY")
        
        # Binance (use secrets provider)
        binance_api_key = get_value("BINANCE_API_KEY")
        binance_api_secret = get_value("BINANCE_API_SECRET")
        
        # Telegram (use secrets provider)
        telegram_bot_token = get_value("TELEGRAM_BOT_TOKEN")
        telegram_default_chat_id = get_value("TELEGRAM_CHAT_ID") or get_value("TELEGRAM_DEFAULT_CHAT_ID")
        
        # PostgreSQL (use secrets provider for password)
        postgres_dsn = get_value("DATABASE_URL") or get_value("POSTGRES_DSN")
        postgres_host = os.getenv("POSTGRES_HOST", "localhost")
        postgres_port = int(os.getenv("POSTGRES_PORT", "5432"))
        postgres_db = os.getenv("POSTGRES_DB", "arbitrage")
        postgres_user = os.getenv("POSTGRES_USER", "arbitrage")
        postgres_password = get_value("POSTGRES_PASSWORD", "arbitrage")
        
        # Redis
        redis_url = os.getenv("REDIS_URL")
        redis_host = os.getenv("REDIS_HOST", "localhost")
        redis_port = int(os.getenv("REDIS_PORT", "6379"))
        redis_db = int(os.getenv("REDIS_DB", "0"))
        
        # Email (SMTP - use secrets provider for password)
        smtp_host = os.getenv("SMTP_HOST")
        smtp_port = int(os.getenv("SMTP_PORT", "587"))
        smtp_user = get_value("SMTP_USER")
        smtp_password = get_value("SMTP_PASSWORD")
        smtp_use_tls = os.getenv("SMTP_USE_TLS", "true").lower() == "true"
        
        # Slack
        slack_webhook_url = os.getenv("SLACK_WEBHOOK_URL")
        
        # Monitoring
        prometheus_enabled = os.getenv("PROMETHEUS_ENABLED", "true").lower() == "true"
        prometheus_port = int(os.getenv("PROMETHEUS_PORT", "9100"))
        grafana_enabled = os.getenv("GRAFANA_ENABLED", "true").lower() == "true"
        
        # Backward compatibility
        app_env = os.getenv("APP_ENV") or os.getenv("ENV")
        
        settings = cls(
            env=env,
            upbit_access_key=upbit_access_key,
            upbit_secret_key=upbit_secret_key,
            binance_api_key=binance_api_key,
            binance_api_secret=binance_api_secret,
            telegram_bot_token=telegram_bot_token,
            telegram_default_chat_id=telegram_default_chat_id,
            postgres_dsn=postgres_dsn,
            postgres_host=postgres_host,
            postgres_port=postgres_port,
            postgres_db=postgres_db,
            postgres_user=postgres_user,
            postgres_password=postgres_password,
            redis_url=redis_url,
            redis_host=redis_host,
            redis_port=redis_port,
            redis_db=redis_db,
            smtp_host=smtp_host,
            smtp_port=smtp_port,
            smtp_user=smtp_user,
            smtp_password=smtp_password,
            smtp_use_tls=smtp_use_tls,
            slack_webhook_url=slack_webhook_url,
            prometheus_enabled=prometheus_enabled,
            prometheus_port=prometheus_port,
            grafana_enabled=grafana_enabled,
            app_env=app_env,
            secrets_provider=secrets_provider,  # D78-2
        )
        
        # Apply overrides (for testing)
        if overrides:
            for key, value in overrides.items():
                if hasattr(settings, key):
                    setattr(settings, key, value)
        
        # Validate
        settings.validate()
        
        return settings
    
    def validate(self) -> None:
        """
        Validate settings based on environment
        
        For local_dev: Allow None/defaults, log warnings
        For paper/live: Fail fast if critical credentials are missing
        """
        if self.env == RuntimeEnv.LOCAL_DEV:
            # Local dev: warnings only
            if not self.telegram_bot_token:
                print("Warning: TELEGRAM_BOT_TOKEN not set (local_dev mode)")
            if not self.upbit_access_key:
                print("Warning: UPBIT_ACCESS_KEY not set (local_dev mode, OK for mock/testing)")
            if not self.binance_api_key:
                print("Warning: BINANCE_API_KEY not set (local_dev mode, OK for mock/testing)")
        
        elif self.env in (RuntimeEnv.PAPER, RuntimeEnv.LIVE):
            # Paper/Live: strict validation
            missing = []
            
            # Exchange credentials (at least one required)
            if not (self.upbit_access_key and self.upbit_secret_key) and \
               not (self.binance_api_key and self.binance_api_secret):
                missing.append("At least one exchange (Upbit or Binance) credentials required")
            
            # Telegram (required for production alerting)
            if not self.telegram_bot_token or not self.telegram_default_chat_id:
                missing.append("TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID required for paper/live")
            
            # Database (required for state persistence)
            if not self.postgres_dsn and not self.postgres_host:
                missing.append("PostgreSQL connection (POSTGRES_DSN or POSTGRES_HOST) required")
            
            if missing:
                error_msg = (
                    f"\n{'='*60}\n"
                    f"CRITICAL: Missing required credentials for {self.env.value} environment:\n"
                    f"{chr(10).join('  - ' + m for m in missing)}\n\n"
                    f"Please set the following environment variables:\n"
                    f"  ARBITRAGE_ENV={self.env.value}\n"
                )
                
                if "Upbit" in str(missing) or "Binance" in str(missing):
                    error_msg += (
                        f"  # Upbit\n"
                        f"  UPBIT_ACCESS_KEY=your_upbit_access_key\n"
                        f"  UPBIT_SECRET_KEY=your_upbit_secret_key\n"
                        f"  # Binance\n"
                        f"  BINANCE_API_KEY=your_binance_api_key\n"
                        f"  BINANCE_API_SECRET=your_binance_api_secret\n"
                    )
                
                if "TELEGRAM" in str(missing):
                    error_msg += (
                        f"  # Telegram\n"
                        f"  TELEGRAM_BOT_TOKEN=your_telegram_bot_token\n"
                        f"  TELEGRAM_CHAT_ID=your_telegram_chat_id\n"
                    )
                
                if "PostgreSQL" in str(missing):
                    error_msg += (
                        f"  # PostgreSQL\n"
                        f"  POSTGRES_DSN=postgresql://user:password@localhost:5432/arbitrage\n"
                        f"  # Or individual params:\n"
                        f"  POSTGRES_HOST=localhost\n"
                        f"  POSTGRES_PORT=5432\n"
                        f"  POSTGRES_DB=arbitrage\n"
                        f"  POSTGRES_USER=arbitrage\n"
                        f"  POSTGRES_PASSWORD=arbitrage\n"
                    )
                
                error_msg += (
                    f"\nAlternatively, create a .env.{self.env.value} file at project root.\n"
                    f"{'='*60}\n"
                )
                
                raise ValueError(error_msg)
    
    def get_postgres_dsn(self) -> str:
        """
        Get PostgreSQL DSN (Data Source Name)
        
        Returns full DSN string for database connection
        """
        if self.postgres_dsn:
            return self.postgres_dsn
        
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )
    
    def get_redis_url(self) -> str:
        """
        Get Redis URL
        
        Returns full Redis URL string
        """
        if self.redis_url:
            return self.redis_url
        
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert settings to dict (for logging/debugging)"""
        return {
            "env": self.env.value,
            "upbit_configured": bool(self.upbit_access_key),
            "binance_configured": bool(self.binance_api_key),
            "telegram_configured": bool(self.telegram_bot_token and self.telegram_default_chat_id),
            "postgres_configured": bool(self.postgres_dsn or self.postgres_host),
            "redis_configured": bool(self.redis_url or self.redis_host),
            "smtp_configured": bool(self.smtp_host and self.smtp_user),
            "slack_configured": bool(self.slack_webhook_url),
            "prometheus_enabled": self.prometheus_enabled,
            "grafana_enabled": self.grafana_enabled,
        }


# Singleton instance
_settings_instance: Optional[Settings] = None


def get_settings(overrides: Optional[Dict[str, Any]] = None, force_reload: bool = False) -> Settings:
    """
    Get settings singleton
    
    Args:
        overrides: Optional overrides for testing
        force_reload: Force reload from environment
    
    Returns:
        Settings instance
    """
    global _settings_instance
    
    if _settings_instance is None or force_reload or overrides:
        _settings_instance = Settings.from_env(overrides=overrides)
    
    return _settings_instance


def reload_settings() -> Settings:
    """
    Force reload settings from environment
    
    Useful when environment variables change at runtime
    """
    return get_settings(force_reload=True)


# For backward compatibility with existing code that uses APP_ENV
def get_app_env() -> str:
    """
    Get APP_ENV value (backward compatibility)
    
    Returns: "development", "production", "staging", etc.
    """
    settings = get_settings()
    
    # Map ARBITRAGE_ENV to APP_ENV
    env_map = {
        RuntimeEnv.LOCAL_DEV: "development",
        RuntimeEnv.PAPER: "staging",  # or "paper"
        RuntimeEnv.LIVE: "production",
    }
    
    # Return app_env if set, otherwise map from ARBITRAGE_ENV
    return settings.app_env or env_map.get(settings.env, "development")
