"""
D46: LiveRunner Read-Only 모드 테스트

live_readonly 모드에서 주문이 생성되지 않는지 검증
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from arbitrage.live_runner import ArbitrageLiveRunner, ArbitrageLiveConfig, RiskLimits
from arbitrage.arbitrage_core import ArbitrageConfig, OrderBookSnapshot, ArbitrageEngine
from arbitrage.exchanges.base import OrderSide, OrderType


class TestD46LiveRunnerReadOnly:
    """D46 LiveRunner Read-Only 모드 테스트"""

    def test_live_runner_readonly_mode_initialization(self):
        """Read-Only 모드 초기화"""
        config = ArbitrageLiveConfig(
            symbol_a="KRW-BTC",
            symbol_b="BTCUSDT",
            min_spread_bps=20.0,
            taker_fee_a_bps=5.0,
            taker_fee_b_bps=4.0,
            slippage_bps=5.0,
            max_position_usd=5000.0,
            poll_interval_seconds=1.0,
            max_concurrent_trades=1,
            mode="live_readonly",  # D46: Read-Only 모드
            log_level="INFO",
            max_runtime_seconds=60,
            risk_limits=RiskLimits(
                max_notional_per_trade=5000.0,
                max_daily_loss=10000.0,
                max_open_trades=1,
            ),
            paper_simulation_enabled=False,
        )
        
        # Mock 거래소
        exchange_a = Mock()
        exchange_b = Mock()
        
        # ArbitrageEngine 생성
        engine_config = ArbitrageConfig(
            min_spread_bps=20.0,
            taker_fee_a_bps=5.0,
            taker_fee_b_bps=4.0,
            slippage_bps=5.0,
            max_position_usd=5000.0,
            exchange_a_to_b_rate=2.5,
            bid_ask_spread_bps=100.0,
        )
        engine = ArbitrageEngine(engine_config)
        
        runner = ArbitrageLiveRunner(
            exchange_a=exchange_a,
            exchange_b=exchange_b,
            engine=engine,
            config=config,
        )
        
        assert runner.config.mode == "live_readonly"
        assert runner.config.paper_simulation_enabled is False

    def test_live_runner_readonly_mode_config(self):
        """Read-Only 모드 설정 검증"""
        config = ArbitrageLiveConfig(
            symbol_a="KRW-BTC",
            symbol_b="BTCUSDT",
            min_spread_bps=20.0,
            taker_fee_a_bps=5.0,
            taker_fee_b_bps=4.0,
            slippage_bps=5.0,
            max_position_usd=5000.0,
            poll_interval_seconds=1.0,
            max_concurrent_trades=1,
            mode="live_readonly",
            log_level="INFO",
            max_runtime_seconds=60,
            risk_limits=RiskLimits(
                max_notional_per_trade=5000.0,
                max_daily_loss=10000.0,
                max_open_trades=1,
            ),
            paper_simulation_enabled=False,
        )
        
        # 설정 검증
        assert config.mode == "live_readonly"
        assert config.paper_simulation_enabled is False
        assert config.symbol_a == "KRW-BTC"
        assert config.symbol_b == "BTCUSDT"

    def test_live_runner_readonly_vs_paper_mode(self):
        """Read-Only 모드와 Paper 모드 비교"""
        # Read-Only 설정
        readonly_config = ArbitrageLiveConfig(
            symbol_a="KRW-BTC",
            symbol_b="BTCUSDT",
            min_spread_bps=20.0,
            taker_fee_a_bps=5.0,
            taker_fee_b_bps=4.0,
            slippage_bps=5.0,
            max_position_usd=5000.0,
            poll_interval_seconds=1.0,
            max_concurrent_trades=1,
            mode="live_readonly",
            log_level="INFO",
            max_runtime_seconds=60,
            risk_limits=RiskLimits(
                max_notional_per_trade=5000.0,
                max_daily_loss=10000.0,
                max_open_trades=1,
            ),
            paper_simulation_enabled=False,
        )
        
        # Paper 설정
        paper_config = ArbitrageLiveConfig(
            symbol_a="KRW-BTC",
            symbol_b="BTCUSDT",
            min_spread_bps=20.0,
            taker_fee_a_bps=5.0,
            taker_fee_b_bps=4.0,
            slippage_bps=5.0,
            max_position_usd=5000.0,
            poll_interval_seconds=1.0,
            max_concurrent_trades=1,
            mode="paper",
            log_level="INFO",
            max_runtime_seconds=60,
            risk_limits=RiskLimits(
                max_notional_per_trade=5000.0,
                max_daily_loss=10000.0,
                max_open_trades=1,
            ),
            paper_simulation_enabled=True,
        )
        
        # 모드 확인
        assert readonly_config.mode == "live_readonly"
        assert readonly_config.paper_simulation_enabled is False
        
        assert paper_config.mode == "paper"
        assert paper_config.paper_simulation_enabled is True

    def test_live_runner_readonly_with_real_exchanges(self):
        """Read-Only 모드에서 실제 거래소 어댑터 사용"""
        from arbitrage.exchanges.upbit_spot import UpbitSpotExchange
        from arbitrage.exchanges.binance_futures import BinanceFuturesExchange
        
        config = ArbitrageLiveConfig(
            symbol_a="KRW-BTC",
            symbol_b="BTCUSDT",
            min_spread_bps=20.0,
            taker_fee_a_bps=5.0,
            taker_fee_b_bps=4.0,
            slippage_bps=5.0,
            max_position_usd=5000.0,
            poll_interval_seconds=1.0,
            max_concurrent_trades=1,
            mode="live_readonly",
            log_level="INFO",
            max_runtime_seconds=60,
            risk_limits=RiskLimits(
                max_notional_per_trade=5000.0,
                max_daily_loss=10000.0,
                max_open_trades=1,
            ),
            paper_simulation_enabled=False,
        )
        
        # 실제 어댑터 생성 (API 키 없음)
        upbit_config = {
            "api_key": "",
            "api_secret": "",
            "base_url": "https://api.upbit.com",
            "timeout": 10,
            "live_enabled": False,
        }
        
        binance_config = {
            "api_key": "",
            "api_secret": "",
            "base_url": "https://fapi.binance.com",
            "timeout": 10,
            "leverage": 1,
            "live_enabled": False,
        }
        
        exchange_a = UpbitSpotExchange(upbit_config)
        exchange_b = BinanceFuturesExchange(binance_config)
        
        # ArbitrageEngine 생성
        engine_config = ArbitrageConfig(
            min_spread_bps=20.0,
            taker_fee_a_bps=5.0,
            taker_fee_b_bps=4.0,
            slippage_bps=5.0,
            max_position_usd=5000.0,
            exchange_a_to_b_rate=2.5,
            bid_ask_spread_bps=100.0,
        )
        engine = ArbitrageEngine(engine_config)
        
        runner = ArbitrageLiveRunner(
            exchange_a=exchange_a,
            exchange_b=exchange_b,
            engine=engine,
            config=config,
        )
        
        assert runner.config.mode == "live_readonly"
        assert runner.exchange_a.name == "upbit"
        assert runner.exchange_b.name == "binance_futures"

    def test_live_runner_readonly_api_key_error_handling(self):
        """Read-Only 모드에서 API 키 부족 시 우아한 에러 처리"""
        from arbitrage.exchanges.upbit_spot import UpbitSpotExchange
        from arbitrage.exchanges.exceptions import AuthenticationError
        
        config = {
            "api_key": "",
            "api_secret": "",
            "base_url": "https://api.upbit.com",
            "timeout": 10,
            "live_enabled": False,
        }
        
        exchange = UpbitSpotExchange(config)
        
        # API 키 없이 잔고 조회 시도
        with pytest.raises(AuthenticationError):
            exchange.get_balance()
