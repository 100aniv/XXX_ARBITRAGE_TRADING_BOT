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
    upbit_access_key: Optional[str] = None
    upbit_secret_key: Optional[str] = None
    binance_api_key: Optional[str] = None
    binance_secret_key: Optional[str] = None
    ws_reconnect_max_attempts: int = 10
    ws_reconnect_delay: int = 1
    ws_max_reconnect_delay: int = 60


@dataclass(frozen=True)
class DatabaseConfig:
    redis_host: str = 'localhost'
    redis_port: int = 6380
    redis_db: int = 0
    redis_password: Optional[str] = None
    postgres_host: str = 'localhost'
    postgres_port: int = 5432
    postgres_database: str = 'arbitrage'
    postgres_user: str = 'arbitrage'
    postgres_password: str = 'arbitrage'
    postgres_pool_min: int = 2
    postgres_pool_max: int = 10


@dataclass(frozen=True)
class RiskConfig:
    max_notional_per_trade: float = 5000.0
    max_open_trades: int = 1
    max_daily_loss: float = 10000.0
    max_daily_trades: int = 100
    position_size_usd: float = 1000.0


@dataclass(frozen=True)
class TradingConfig:
    min_spread_bps: float = 20.0
    taker_fee_a_bps: float = 10.0
    taker_fee_b_bps: float = 10.0
    slippage_bps: float = 5.0
    exchange_a_to_b_rate: float = 2.5
    bid_ask_spread_bps: float = 100.0
    close_on_spread_reversal: bool = True
    min_exit_spread_bps: Optional[float] = None


@dataclass(frozen=True)
class MonitoringConfig:
    log_level: str = 'INFO'
    log_dir: Path = field(default_factory=lambda: Path('logs'))
    log_rotation: str = '1 day'
    log_retention: str = '30 days'
    metrics_enabled: bool = True
    metrics_interval_seconds: int = 60
    health_check_enabled: bool = True
    health_check_interval_seconds: int = 30


@dataclass(frozen=True)
class SessionConfig:
    mode: str = 'paper'
    data_source: str = 'paper'
    max_runtime_seconds: Optional[int] = None
    loop_interval_ms: int = 100
    state_persistence_enabled: bool = True
    snapshot_interval_seconds: int = 300


@dataclass(frozen=True)
class ArbitrageConfig:
    env: str
    exchange: ExchangeConfig
    database: DatabaseConfig
    risk: RiskConfig
    trading: TradingConfig
    monitoring: MonitoringConfig
    session: SessionConfig
    symbols: List[str] = field(default_factory=lambda: ['KRW-BTC'])
    paper_initial_balance_krw: float = 1_000_000.0
    paper_initial_balance_usdt: float = 1_000.0
    
    def to_legacy_config(self):
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


class ConfigError(Exception):
    pass
