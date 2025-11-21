"""
Base Configuration Models (Dataclass-based)

SSOT (Single Source of Truth) for all configuration parameters.
Python 3.7+ compatible, no external dependencies.
"""

from dataclasses import dataclass, field
from typing import Optional, List
from pathlib import Path
import os

try:
    from typing import Literal
except ImportError:
    from typing_extensions import Literal


@dataclass(frozen=True)
class ExchangeConfig:
    """거래소 연결 설정"""
    
    # Upbit
    upbit_access_key: Optional[str] = None
    upbit_secret_key: Optional[str] = None
    
    # Binance
    binance_api_key: Optional[str] = None
    binance_secret_key: Optional[str] = None
    
    # Connection settings
    ws_reconnect_max_attempts: int = 10
    ws_reconnect_delay: int = 1
    ws_max_reconnect_delay: int = 60
    
    def __post_init__(self):
        """환경변수 치환"""
        # frozen dataclass이므로 object.__setattr__ 사용
        for attr_name in ['upbit_access_key', 'upbit_secret_key', 'binance_api_key', 'binance_secret_key']:
            value = getattr(self, attr_name)
            if value and value.startswith('${') and value.endswith('}'):
                env_var = value[2:-1]
                new_value = os.getenv(env_var, value)
                object.__setattr__(self, attr_name, new_value)


@dataclass(frozen=True)
class DatabaseConfig:
    """데이터베이스 연결 설정"""
    
    # Redis
    redis_host: str = 'localhost'
    redis_port: int = 6380
    redis_db: int = 0
    redis_password: Optional[str] = None
    
    # PostgreSQL
    postgres_host: str = 'localhost'
    postgres_port: int = 5432
    postgres_database: str = 'arbitrage'
    postgres_user: str = 'arbitrage'
    postgres_password: str = 'arbitrage'
    
    # Connection pool
    postgres_pool_min: int = 2
    postgres_pool_max: int = 10
    
    def __post_init__(self):
        """환경변수 치환"""
        for attr_name in ['redis_password', 'postgres_password', 'redis_host', 'postgres_host']:
            value = getattr(self, attr_name)
            if value and isinstance(value, str) and value.startswith('${') and value.endswith('}'):
                env_var = value[2:-1]
                new_value = os.getenv(env_var, value)
                object.__setattr__(self, attr_name, new_value)


@dataclass(frozen=True)
class RiskConfig:
    """리스크 관리 설정"""
    
    # Per-trade limits
    max_notional_per_trade: float = 5000.0
    max_open_trades: int = 1
    
    # Daily limits
    max_daily_loss: float = 1000.0
    max_daily_trades: int = 100
    
    # Position sizing
    position_size_usd: float = 1000.0
    
    def __post_init__(self):
        """Validation"""
        if self.max_daily_loss < self.max_notional_per_trade:
            raise ValueError(
                f"max_daily_loss ({self.max_daily_loss}) must be >= "
                f"max_notional_per_trade ({self.max_notional_per_trade})"
            )


@dataclass(frozen=True)
class TradingConfig:
    """거래 전략 설정"""
    
    # Spread & Fees
    min_spread_bps: float = 20.0
    taker_fee_a_bps: float = 10.0
    taker_fee_b_bps: float = 10.0
    slippage_bps: float = 5.0
    
    # Exchange rate
    exchange_a_to_b_rate: float = 2.5
    bid_ask_spread_bps: float = 100.0
    
    # Exit strategy
    close_on_spread_reversal: bool = True
    min_exit_spread_bps: Optional[float] = None
    
    def __post_init__(self):
        """Spread vs fees validation"""
        total_cost = self.taker_fee_a_bps + self.taker_fee_b_bps + self.slippage_bps
        
        if self.min_spread_bps <= total_cost * 1.5:
            raise ValueError(
                f"min_spread_bps ({self.min_spread_bps}) must be > 1.5 * (fees + slippage) ({total_cost * 1.5:.2f}). "
                f"Current: fee_a={self.taker_fee_a_bps}, fee_b={self.taker_fee_b_bps}, slippage={self.slippage_bps}"
            )


@dataclass(frozen=True)
class MonitoringConfig:
    """모니터링 및 로깅 설정"""
    
    # Logging
    log_level: str = 'INFO'  # 'DEBUG', 'INFO', 'WARNING', 'ERROR'
    log_dir: Path = field(default_factory=lambda: Path('logs'))
    log_rotation: str = '1 day'
    log_retention: str = '30 days'
    
    # Metrics
    metrics_enabled: bool = True
    metrics_interval_seconds: int = 60
    
    # Health check
    health_check_enabled: bool = True
    health_check_interval_seconds: int = 30
    
    def __post_init__(self):
        """Log directory 생성"""
        if not self.log_dir.exists():
            self.log_dir.mkdir(parents=True, exist_ok=True)


@dataclass(frozen=True)
class SessionConfig:
    """세션 관리 설정"""
    
    mode: str = 'paper'  # 'paper', 'live', 'backtest'
    data_source: str = 'paper'  # 'paper', 'ws', 'backtest'
    
    # Runtime
    max_runtime_seconds: Optional[int] = None
    loop_interval_ms: int = 100
    
    # State persistence
    state_persistence_enabled: bool = True
    snapshot_interval_seconds: int = 300


@dataclass(frozen=True)
class ArbitrageConfig:
    """
    Arbitrage Trading System Configuration (SSOT)
    
    통합 설정 모델. 모든 하위 설정을 포함.
    """
    
    # Environment
    env: str  # 'development', 'staging', 'production'
    
    # Sub-configurations
    exchange: ExchangeConfig
    database: DatabaseConfig
    risk: RiskConfig
    trading: TradingConfig
    monitoring: MonitoringConfig
    session: SessionConfig
    
    # Symbols
    symbols: List[str] = field(default_factory=lambda: ['KRW-BTC'])
    
    # Paper trading
    paper_initial_balance_krw: float = 1_000_000.0
    paper_initial_balance_usdt: float = 1_000.0
    
    def __post_init__(self):
        """Validation"""
        if not self.symbols:
            raise ValueError("symbols must contain at least one symbol")
    
    def to_legacy_config(self):
        """
        기존 ArbitrageConfig (arbitrage_core.py)로 변환
        
        Migration helper - D72-1에서만 사용, 향후 제거 예정
        """
        from arbitrage.arbitrage_core import ArbitrageConfig as LegacyConfig
        
        return LegacyConfig(
            min_spread_bps=self.trading.min_spread_bps,
            taker_fee_a_bps=self.trading.taker_fee_a_bps,
            taker_fee_b_bps=self.trading.taker_fee_b_bps,
            slippage_bps=self.trading.slippage_bps,
            max_position_usd=self.risk.max_notional_per_trade,
            max_open_trades=self.risk.max_open_trades,
            close_on_spread_reversal=self.trading.close_on_spread_reversal,
            exchange_a_to_b_rate=self.trading.exchange_a_to_b_rate,
            bid_ask_spread_bps=self.trading.bid_ask_spread_bps
        )
    
    def to_live_config(self):
        """
        기존 ArbitrageLiveConfig (live_runner.py)로 변환
        
        Migration helper - D72-1에서만 사용, 향후 제거 예정
        """
        from arbitrage.live_runner import ArbitrageLiveConfig as LegacyLiveConfig
        
        # 첫 번째 심볼을 기본으로 사용
        symbol_a = self.symbols[0] if self.symbols else 'KRW-BTC'
        # 매핑 (예: KRW-BTC -> BTCUSDT)
        symbol_b = symbol_a.replace('KRW-', '') + 'USDT'
        
        return LegacyLiveConfig(
            symbol_a=symbol_a,
            symbol_b=symbol_b,
            mode=self.session.mode,
            data_source=self.session.data_source,
            loop_interval_ms=self.session.loop_interval_ms,
            max_runtime_seconds=self.session.max_runtime_seconds
        )
    
    def to_risk_limits(self):
        """
        기존 RiskLimits (live_runner.py)로 변환
        
        Migration helper - D72-1에서만 사용, 향후 제거 예정
        """
        from arbitrage.live_runner import RiskLimits
        
        return RiskLimits(
            max_notional_per_trade=self.risk.max_notional_per_trade,
            max_daily_loss=self.risk.max_daily_loss,
            max_open_trades=self.risk.max_open_trades
        )


class ConfigError(Exception):
    """Configuration 관련 예외"""
    pass
