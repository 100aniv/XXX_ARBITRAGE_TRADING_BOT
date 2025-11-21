"""Staging Environment Configuration"""

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


def get_staging_config() -> ArbitrageConfig:
    """
    Staging 환경 설정
    
    특징:
    - Production과 유사한 설정
    - 실제 WS 연결 테스트
    - Paper mode 유지
    - 중간 리스크 한도
    - INFO 로깅
    """
    
    return ArbitrageConfig(
        env='staging',
        
        exchange=ExchangeConfig(
            # Staging에서는 read-only API keys 사용 가능
            upbit_access_key='${UPBIT_ACCESS_KEY}',
            upbit_secret_key='${UPBIT_SECRET_KEY}',
            binance_api_key='${BINANCE_API_KEY}',
            binance_secret_key='${BINANCE_SECRET_KEY}',
            
            ws_reconnect_max_attempts=10,
            ws_reconnect_delay=1,
            ws_max_reconnect_delay=60
        ),
        
        database=DatabaseConfig(
            redis_host='localhost',  # Staging도 로컬 (또는 staging 전용 host)
            redis_port=6380,
            redis_db=1,  # DB 분리
            redis_password='${REDIS_PASSWORD}',
            
            postgres_host='localhost',
            postgres_port=5432,
            postgres_database='arbitrage_staging',
            postgres_user='arbitrage',
            postgres_password='${POSTGRES_PASSWORD}',
            
            postgres_pool_min=3,
            postgres_pool_max=10
        ),
        
        risk=RiskConfig(
            max_notional_per_trade=10000.0,
            max_open_trades=2,
            max_daily_loss=20000.0,
            max_daily_trades=200,
            position_size_usd=2000.0
        ),
        
        trading=TradingConfig(
            min_spread_bps=25.0,  # 약간 보수적
            taker_fee_a_bps=10.0,
            taker_fee_b_bps=10.0,
            slippage_bps=10.0,  # 실제에 가까운 slippage
            exchange_a_to_b_rate=2.5,
            bid_ask_spread_bps=100.0,
            close_on_spread_reversal=True,
            min_exit_spread_bps=5.0
        ),
        
        monitoring=MonitoringConfig(
            log_level='INFO',
            log_dir=Path('logs/staging'),
            log_rotation='1 day',
            log_retention='30 days',
            
            metrics_enabled=True,
            metrics_interval_seconds=60,
            
            health_check_enabled=True,
            health_check_interval_seconds=30
        ),
        
        session=SessionConfig(
            mode='paper',  # Staging도 Paper mode
            data_source='ws',  # 실제 WS 데이터
            max_runtime_seconds=None,
            loop_interval_ms=100,
            state_persistence_enabled=True,
            snapshot_interval_seconds=300
        ),
        
        symbols=['KRW-BTC', 'KRW-ETH'],  # 멀티 심볼 테스트
        
        paper_initial_balance_krw=10_000_000.0,
        paper_initial_balance_usdt=10_000.0
    )
