"""
Configuration Loader

ENV 환경변수 기반으로 자동으로 적절한 Config를 로드합니다.
"""

import os
import logging
from typing import Optional, Literal
from config.base import ArbitrageConfig, ConfigError
from config.environments.development import get_development_config
from config.environments.staging import get_staging_config
from config.environments.production import get_production_config

logger = logging.getLogger(__name__)

# Environment 타입
EnvType = Literal['development', 'staging', 'production']


def get_current_env() -> EnvType:
    """
    현재 환경 감지
    
    우선순위:
    1. ENV 환경변수
    2. ARBITRAGE_ENV 환경변수
    3. 기본값: development
    
    Returns:
        현재 환경 ('development', 'staging', 'production')
    """
    env = os.getenv('ENV') or os.getenv('ARBITRAGE_ENV') or 'development'
    env = env.lower()
    
    if env not in ['development', 'staging', 'production']:
        logger.warning(
            f"Invalid environment '{env}', falling back to 'development'. "
            f"Valid values: development, staging, production"
        )
        env = 'development'
    
    return env  # type: ignore


def load_config(env: Optional[EnvType] = None) -> ArbitrageConfig:
    """
    환경에 맞는 Config 로드
    
    Args:
        env: 환경 지정 (None이면 자동 감지)
    
    Returns:
        ArbitrageConfig 인스턴스
    
    Raises:
        ConfigError: Config 로드 실패 시
    
    Examples:
        >>> # 자동 감지 (ENV 환경변수 기반)
        >>> config = load_config()
        
        >>> # 명시적 지정
        >>> config = load_config(env='production')
    """
    if env is None:
        env = get_current_env()
    
    logger.info(f"[CONFIG] Loading configuration for environment: {env}")
    
    try:
        if env == 'development':
            config = get_development_config()
        elif env == 'staging':
            config = get_staging_config()
        elif env == 'production':
            config = get_production_config()
        else:
            raise ConfigError(f"Unknown environment: {env}")
        
        # Validation
        _validate_config(config)
        
        logger.info(
            f"[CONFIG] ✅ Configuration loaded successfully: "
            f"env={config.env}, mode={config.session.mode}, "
            f"symbols={config.symbols}, risk_max_notional={config.risk.max_notional_per_trade}"
        )
        
        return config
    
    except Exception as e:
        logger.error(f"[CONFIG] ❌ Failed to load configuration: {e}")
        raise ConfigError(f"Configuration loading failed: {e}") from e


def _validate_config(config: ArbitrageConfig) -> None:
    """
    Config 추가 검증
    
    Pydantic validation 외에 비즈니스 로직 검증 수행
    
    Args:
        config: 검증할 Config
    
    Raises:
        ConfigError: 검증 실패 시
    """
    # 1. Production에서는 secrets 필수
    if config.env == 'production':
        if config.session.mode == 'live':
            # Live mode에서는 API keys 필수
            if not config.exchange.upbit_access_key or config.exchange.upbit_access_key.startswith('${'):
                raise ConfigError("Production live mode requires UPBIT_ACCESS_KEY environment variable")
            
            if not config.exchange.binance_api_key or config.exchange.binance_api_key.startswith('${'):
                raise ConfigError("Production live mode requires BINANCE_API_KEY environment variable")
        
        # Database passwords 필수
        if not config.database.redis_password or config.database.redis_password.startswith('${'):
            logger.warning("Production Redis password not set, using None")
        
        if not config.database.postgres_password or config.database.postgres_password.startswith('${'):
            raise ConfigError("Production requires POSTGRES_PASSWORD environment variable")
    
    # 2. Log directory 생성 가능 여부
    try:
        config.monitoring.log_dir.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        raise ConfigError(f"Cannot create log directory {config.monitoring.log_dir}: {e}")
    
    # 3. 심볼 목록 검증
    if not config.symbols:
        raise ConfigError("symbols list cannot be empty")
    
    for symbol in config.symbols:
        if not symbol or not isinstance(symbol, str):
            raise ConfigError(f"Invalid symbol: {symbol}")
    
    # 4. Spread vs Fees 검증 (이미 Pydantic에서 검증하지만 추가 확인)
    total_cost = (
        config.trading.taker_fee_a_bps +
        config.trading.taker_fee_b_bps +
        config.trading.slippage_bps
    )
    
    if config.trading.min_spread_bps <= total_cost * 1.5:
        raise ConfigError(
            f"min_spread_bps ({config.trading.min_spread_bps}) must be > 1.5 * total_cost ({total_cost * 1.5:.2f})"
        )
    
    logger.debug(f"[CONFIG] Validation passed: {config.env}")


def reload_config(env: Optional[EnvType] = None) -> ArbitrageConfig:
    """
    Config 재로드
    
    환경변수가 변경되었을 때 사용
    
    Args:
        env: 환경 지정
    
    Returns:
        새로 로드된 ArbitrageConfig
    """
    logger.info("[CONFIG] Reloading configuration...")
    return load_config(env=env)
