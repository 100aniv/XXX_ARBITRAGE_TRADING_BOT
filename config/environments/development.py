"""Development Environment Configuration"""

from pathlib import Path
from config.base import (
    ArbitrageConfig,
    ExchangeConfig,
    DatabaseConfig,
    RiskConfig,
    TradingConfig,
    MonitoringConfig,
    SessionConfig
)


def get_development_config() -> ArbitrageConfig:
    """
    Development 환경 설정
    
    특징:
    - 낮은 리스크 한도
    - Debug 로깅
    - Paper mode 기본
    - 로컬 Redis/PostgreSQL
    - Secrets 불필요 (Paper mode)
    """
    
    return ArbitrageConfig(
        env='development',
        
        exchange=ExchangeConfig(
            # Development에서는 API keys 불필요 (Paper mode)
            upbit_access_key=None,
            upbit_secret_key=None,
            binance_api_key=None,
            binance_secret_key=None,
            
            ws_reconnect_max_attempts=5,  # 빠른 테스트를 위해 낮춤
            ws_reconnect_delay=1,
            ws_max_reconnect_delay=30
        ),
        
        database=DatabaseConfig(
            redis_host='localhost',
            redis_port=6380,
            redis_db=0,
            redis_password=None,  # Development는 password 없음
            
            postgres_host='localhost',
            postgres_port=5432,
            postgres_database='arbitrage',
            postgres_user='arbitrage',
            postgres_password='arbitrage',
            
            postgres_pool_min=2,
            postgres_pool_max=5  # Development는 작은 pool
        ),
        
        risk=RiskConfig(
            max_notional_per_trade=5000.0,  # 낮은 한도
            max_open_trades=1,
            max_daily_loss=10000.0,
            max_daily_trades=100,
            position_size_usd=1000.0
        ),
        
        trading=TradingConfig(
            min_spread_bps=40.0,  # > 1.5 * (10 + 10 + 5) = 37.5
            taker_fee_a_bps=10.0,
            taker_fee_b_bps=10.0,
            slippage_bps=5.0,
            exchange_a_to_b_rate=2.5,
            bid_ask_spread_bps=100.0,
            close_on_spread_reversal=True,
            min_exit_spread_bps=None
        ),
        
        monitoring=MonitoringConfig(
            log_level='DEBUG',  # Development는 DEBUG
            log_dir=Path('logs'),
            log_rotation='1 day',
            log_retention='7 days',  # 짧은 보관
            
            metrics_enabled=True,
            metrics_interval_seconds=60,
            
            health_check_enabled=True,
            health_check_interval_seconds=30
        ),
        
        session=SessionConfig(
            mode='paper',
            data_source='paper',
            max_runtime_seconds=None,  # 무제한
            loop_interval_ms=100,
            state_persistence_enabled=True,
            snapshot_interval_seconds=300
        ),
        
        symbols=['KRW-BTC'],  # 단일 심볼
        
        paper_initial_balance_krw=1_000_000.0,
        paper_initial_balance_usdt=1_000.0
    )
