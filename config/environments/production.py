"""Production Environment Configuration"""

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


def get_production_config() -> ArbitrageConfig:
    """
    Production 환경 설정
    
    특징:
    - 모든 secrets 환경변수에서 로드 (필수)
    - 엄격한 validation
    - WARNING 로깅 (성능 고려)
    - 실제 WS 데이터
    - Production DB/Redis
    
    ⚠️ 주의:
    - 모든 API keys는 환경변수로 설정 필수
    - mode='live'로 설정 시 실거래 발생
    - 현재는 Paper mode 유지 (실거래 전 충분한 검증 필요)
    """
    
    return ArbitrageConfig(
        env='production',
        
        exchange=ExchangeConfig(
            # Production: 환경변수 필수
            upbit_access_key='${UPBIT_ACCESS_KEY}',
            upbit_secret_key='${UPBIT_SECRET_KEY}',
            binance_api_key='${BINANCE_API_KEY}',
            binance_secret_key='${BINANCE_SECRET_KEY}',
            
            ws_reconnect_max_attempts=10,
            ws_reconnect_delay=1,
            ws_max_reconnect_delay=60
        ),
        
        database=DatabaseConfig(
            redis_host='${REDIS_HOST}',  # Production host
            redis_port=6380,
            redis_db=0,
            redis_password='${REDIS_PASSWORD}',
            
            postgres_host='${POSTGRES_HOST}',
            postgres_port=5432,
            postgres_database='arbitrage_prod',
            postgres_user='${POSTGRES_USER}',
            postgres_password='${POSTGRES_PASSWORD}',
            
            postgres_pool_min=5,
            postgres_pool_max=20
        ),
        
        risk=RiskConfig(
            # Production: 보수적인 리스크 한도
            max_notional_per_trade=5000.0,
            max_open_trades=1,
            max_daily_loss=10000.0,
            max_daily_trades=50,  # 낮게 설정
            position_size_usd=1000.0
        ),
        
        trading=TradingConfig(
            min_spread_bps=30.0,  # 보수적
            taker_fee_a_bps=10.0,
            taker_fee_b_bps=10.0,
            slippage_bps=15.0,  # 실제 slippage 고려
            exchange_a_to_b_rate=2.5,
            bid_ask_spread_bps=100.0,
            close_on_spread_reversal=True,
            min_exit_spread_bps=10.0
        ),
        
        monitoring=MonitoringConfig(
            log_level='WARNING',  # Production은 WARNING (성능)
            log_dir=Path('/var/log/arbitrage'),  # Production log path
            log_rotation='1 day',
            log_retention='90 days',  # 긴 보관
            
            metrics_enabled=True,
            metrics_interval_seconds=60,
            
            health_check_enabled=True,
            health_check_interval_seconds=30
        ),
        
        session=SessionConfig(
            mode='paper',  # ⚠️ Production도 현재는 Paper (실거래 전 충분한 검증 필요)
            data_source='ws',  # 실제 WS
            max_runtime_seconds=None,
            loop_interval_ms=100,
            state_persistence_enabled=True,
            snapshot_interval_seconds=300
        ),
        
        symbols=['KRW-BTC'],  # Production: 검증된 심볼만
        
        paper_initial_balance_krw=100_000_000.0,  # 실제 규모로 테스트
        paper_initial_balance_usdt=100_000.0
    )
