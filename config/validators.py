"""
Configuration Validators

비즈니스 로직 기반 추가 검증 규칙
"""

from typing import Optional
from config.base import ArbitrageConfig, ConfigError


def validate_spread_profitability(config: ArbitrageConfig) -> bool:
    """
    스프레드가 수익을 낼 수 있는지 검증
    
    조건:
    - min_spread_bps > (fee_a + fee_b + slippage) * 안전계수(1.5)
    
    Args:
        config: 검증할 Config
    
    Returns:
        True if valid
    
    Raises:
        ConfigError: 검증 실패 시
    """
    total_cost_bps = (
        config.trading.taker_fee_a_bps +
        config.trading.taker_fee_b_bps +
        config.trading.slippage_bps
    )
    
    min_required_spread = total_cost_bps * 1.5
    
    if config.trading.min_spread_bps <= min_required_spread:
        raise ConfigError(
            f"Spread not profitable: min_spread_bps ({config.trading.min_spread_bps}) "
            f"must be > {min_required_spread:.2f} bps "
            f"(1.5 * (fee_a={config.trading.taker_fee_a_bps} + "
            f"fee_b={config.trading.taker_fee_b_bps} + "
            f"slippage={config.trading.slippage_bps}))"
        )
    
    return True


def validate_risk_constraints(config: ArbitrageConfig) -> bool:
    """
    리스크 제약 조건 검증
    
    조건:
    - max_daily_loss >= max_notional_per_trade
    - max_notional_per_trade > 0
    - max_open_trades >= 1
    
    Args:
        config: 검증할 Config
    
    Returns:
        True if valid
    
    Raises:
        ConfigError: 검증 실패 시
    """
    if config.risk.max_daily_loss < config.risk.max_notional_per_trade:
        raise ConfigError(
            f"max_daily_loss ({config.risk.max_daily_loss}) must be >= "
            f"max_notional_per_trade ({config.risk.max_notional_per_trade})"
        )
    
    if config.risk.max_notional_per_trade <= 0:
        raise ConfigError(f"max_notional_per_trade must be > 0")
    
    if config.risk.max_open_trades < 1:
        raise ConfigError(f"max_open_trades must be >= 1")
    
    return True


def validate_production_secrets(config: ArbitrageConfig) -> bool:
    """
    Production 환경에서 secrets 검증
    
    조건:
    - Live mode: API keys 필수
    - Database passwords 필수
    
    Args:
        config: 검증할 Config
    
    Returns:
        True if valid
    
    Raises:
        ConfigError: 검증 실패 시
    """
    if config.env != 'production':
        return True  # Non-production은 검증 생략
    
    # Live mode에서는 API keys 필수
    if config.session.mode == 'live':
        if not config.exchange.upbit_access_key or config.exchange.upbit_access_key.startswith('${'):
            raise ConfigError(
                "Production live mode requires UPBIT_ACCESS_KEY environment variable. "
                "Please set: export UPBIT_ACCESS_KEY=your_key"
            )
        
        if not config.exchange.binance_api_key or config.exchange.binance_api_key.startswith('${'):
            raise ConfigError(
                "Production live mode requires BINANCE_API_KEY environment variable. "
                "Please set: export BINANCE_API_KEY=your_key"
            )
    
    # PostgreSQL password 필수
    if not config.database.postgres_password or config.database.postgres_password.startswith('${'):
        raise ConfigError(
            "Production requires POSTGRES_PASSWORD environment variable. "
            "Please set: export POSTGRES_PASSWORD=your_password"
        )
    
    return True


def validate_session_config(config: ArbitrageConfig) -> bool:
    """
    세션 설정 검증
    
    조건:
    - mode와 data_source 조합 검증
    - loop_interval_ms 범위 검증
    
    Args:
        config: 검증할 Config
    
    Returns:
        True if valid
    
    Raises:
        ConfigError: 검증 실패 시
    """
    # mode와 data_source 조합 검증
    valid_combinations = {
        'paper': ['paper', 'ws'],
        'live': ['ws'],
        'backtest': ['backtest']
    }
    
    if config.session.data_source not in valid_combinations.get(config.session.mode, []):
        raise ConfigError(
            f"Invalid combination: mode={config.session.mode}, data_source={config.session.data_source}. "
            f"Valid data_source for {config.session.mode}: {valid_combinations[config.session.mode]}"
        )
    
    # Loop interval 검증
    if not (10 <= config.session.loop_interval_ms <= 10000):
        raise ConfigError(
            f"loop_interval_ms ({config.session.loop_interval_ms}) must be between 10 and 10000"
        )
    
    return True


def validate_all(config: ArbitrageConfig) -> bool:
    """
    모든 validator 실행
    
    Args:
        config: 검증할 Config
    
    Returns:
        True if all validations pass
    
    Raises:
        ConfigError: 검증 실패 시
    """
    validate_spread_profitability(config)
    validate_risk_constraints(config)
    validate_production_secrets(config)
    validate_session_config(config)
    
    return True
