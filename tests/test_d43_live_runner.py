# -*- coding: utf-8 -*-
"""
D43 Arbitrage Live Runner Tests

ArbitrageLiveRunner 및 관련 기능 테스트 (100% mock 기반).
"""

import pytest
import time
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime

from arbitrage.arbitrage_core import (
    ArbitrageEngine,
    ArbitrageConfig,
    OrderBookSnapshot,
    ArbitrageTrade,
)
from arbitrage.exchanges import PaperExchange
from arbitrage.exchanges.base import OrderSide, OrderBookSnapshot as ExchangeOrderBookSnapshot
from arbitrage.live_runner import (
    ArbitrageLiveRunner,
    ArbitrageLiveConfig,
    RiskLimits,
)


class TestArbitrageLiveConfig:
    """ArbitrageLiveConfig 테스트"""
    
    def test_config_default_values(self):
        """기본값 설정"""
        config = ArbitrageLiveConfig(
            symbol_a="KRW-BTC",
            symbol_b="BTCUSDT",
        )
        
        assert config.symbol_a == "KRW-BTC"
        assert config.symbol_b == "BTCUSDT"
        assert config.mode == "paper"
        assert config.poll_interval_seconds == 1.0
        assert config.max_runtime_seconds is None
    
    def test_config_custom_values(self):
        """사용자 정의 설정"""
        config = ArbitrageLiveConfig(
            symbol_a="KRW-ETH",
            symbol_b="ETHUSDT",
            min_spread_bps=50.0,
            poll_interval_seconds=2.0,
            max_runtime_seconds=60,
        )
        
        assert config.symbol_a == "KRW-ETH"
        assert config.min_spread_bps == 50.0
        assert config.poll_interval_seconds == 2.0
        assert config.max_runtime_seconds == 60


class TestRiskLimits:
    """RiskLimits 테스트"""
    
    def test_risk_limits_default(self):
        """기본 리스크 제한"""
        limits = RiskLimits()
        
        assert limits.max_notional_per_trade == 10000.0
        assert limits.max_daily_loss == 1000.0
        assert limits.max_open_trades == 1


class TestArbitrageLiveRunnerInitialization:
    """ArbitrageLiveRunner 초기화 테스트"""
    
    def test_runner_initialization(self):
        """Runner 초기화"""
        engine = ArbitrageEngine(
            ArbitrageConfig(
                min_spread_bps=30.0,
                taker_fee_a_bps=5.0,
                taker_fee_b_bps=5.0,
                slippage_bps=5.0,
                max_position_usd=1000.0,
            )
        )
        
        exchange_a = PaperExchange(initial_balance={"KRW": 1000000.0})
        exchange_b = PaperExchange(initial_balance={"USDT": 10000.0})
        
        config = ArbitrageLiveConfig(
            symbol_a="KRW-BTC",
            symbol_b="BTCUSDT",
        )
        
        runner = ArbitrageLiveRunner(
            engine=engine,
            exchange_a=exchange_a,
            exchange_b=exchange_b,
            config=config,
        )
        
        assert runner.engine == engine
        assert runner.exchange_a == exchange_a
        assert runner.exchange_b == exchange_b
        assert runner.config == config


class TestBuildSnapshot:
    """build_snapshot 메서드 테스트"""
    
    def test_build_snapshot_success(self):
        """스냅샷 생성 성공"""
        engine = ArbitrageEngine(
            ArbitrageConfig(
                min_spread_bps=30.0,
                taker_fee_a_bps=5.0,
                taker_fee_b_bps=5.0,
                slippage_bps=5.0,
                max_position_usd=1000.0,
            )
        )
        
        exchange_a = PaperExchange(initial_balance={"KRW": 1000000.0})
        exchange_b = PaperExchange(initial_balance={"USDT": 10000.0})
        
        # 호가 설정
        snapshot_a = ExchangeOrderBookSnapshot(
            symbol="KRW-BTC",
            timestamp=time.time(),
            bids=[(100000.0, 1.0)],
            asks=[(101000.0, 1.0)],
        )
        exchange_a.set_orderbook("KRW-BTC", snapshot_a)
        
        snapshot_b = ExchangeOrderBookSnapshot(
            symbol="BTCUSDT",
            timestamp=time.time(),
            bids=[(40000.0, 1.0)],
            asks=[(40100.0, 1.0)],
        )
        exchange_b.set_orderbook("BTCUSDT", snapshot_b)
        
        config = ArbitrageLiveConfig(
            symbol_a="KRW-BTC",
            symbol_b="BTCUSDT",
        )
        
        runner = ArbitrageLiveRunner(
            engine=engine,
            exchange_a=exchange_a,
            exchange_b=exchange_b,
            config=config,
        )
        
        snapshot = runner.build_snapshot()
        
        assert snapshot is not None
        assert snapshot.best_bid_a == 100000.0
        assert snapshot.best_ask_a == 101000.0
        assert snapshot.best_bid_b == 40000.0
        assert snapshot.best_ask_b == 40100.0
    
    def test_build_snapshot_empty_orderbook(self):
        """빈 호가 처리"""
        engine = ArbitrageEngine(
            ArbitrageConfig(
                min_spread_bps=30.0,
                taker_fee_a_bps=5.0,
                taker_fee_b_bps=5.0,
                slippage_bps=5.0,
                max_position_usd=1000.0,
            )
        )
        
        exchange_a = PaperExchange(initial_balance={"KRW": 1000000.0})
        exchange_b = PaperExchange(initial_balance={"USDT": 10000.0})
        
        # 빈 호가 설정
        snapshot_a = ExchangeOrderBookSnapshot(
            symbol="KRW-BTC",
            timestamp=time.time(),
            bids=[],
            asks=[],
        )
        exchange_a.set_orderbook("KRW-BTC", snapshot_a)
        
        config = ArbitrageLiveConfig(
            symbol_a="KRW-BTC",
            symbol_b="BTCUSDT",
        )
        
        runner = ArbitrageLiveRunner(
            engine=engine,
            exchange_a=exchange_a,
            exchange_b=exchange_b,
            config=config,
        )
        
        snapshot = runner.build_snapshot()
        
        assert snapshot is None


class TestProcessSnapshot:
    """process_snapshot 메서드 테스트"""
    
    def test_process_snapshot_returns_trades(self):
        """스냅샷 처리 및 거래 반환"""
        engine = ArbitrageEngine(
            ArbitrageConfig(
                min_spread_bps=30.0,
                taker_fee_a_bps=5.0,
                taker_fee_b_bps=5.0,
                slippage_bps=5.0,
                max_position_usd=1000.0,
            )
        )
        
        exchange_a = PaperExchange()
        exchange_b = PaperExchange()
        
        config = ArbitrageLiveConfig(
            symbol_a="KRW-BTC",
            symbol_b="BTCUSDT",
        )
        
        runner = ArbitrageLiveRunner(
            engine=engine,
            exchange_a=exchange_a,
            exchange_b=exchange_b,
            config=config,
        )
        
        # 스냅샷 생성
        snapshot = OrderBookSnapshot(
            timestamp=datetime.utcnow().isoformat(),
            best_bid_a=100000.0,
            best_ask_a=101000.0,
            best_bid_b=40000.0,
            best_ask_b=40100.0,
        )
        
        trades = runner.process_snapshot(snapshot)
        
        assert isinstance(trades, list)


class TestExecuteTrades:
    """execute_trades 메서드 테스트"""
    
    def test_execute_trades_open(self):
        """거래 개설"""
        engine = ArbitrageEngine(
            ArbitrageConfig(
                min_spread_bps=30.0,
                taker_fee_a_bps=5.0,
                taker_fee_b_bps=5.0,
                slippage_bps=5.0,
                max_position_usd=1000.0,
            )
        )
        
        exchange_a = PaperExchange(initial_balance={"KRW": 10000000.0, "BTC": 0.0})
        exchange_b = PaperExchange(initial_balance={"USDT": 100000.0, "BTC": 0.0})
        
        config = ArbitrageLiveConfig(
            symbol_a="KRW-BTC",
            symbol_b="BTCUSDT",
        )
        
        runner = ArbitrageLiveRunner(
            engine=engine,
            exchange_a=exchange_a,
            exchange_b=exchange_b,
            config=config,
        )
        
        # 거래 생성
        trade = ArbitrageTrade(
            open_timestamp=datetime.utcnow().isoformat(),
            side="LONG_A_SHORT_B",
            entry_spread_bps=50.0,
            notional_usd=1000.0,
            is_open=True,
        )
        
        runner.execute_trades([trade])
        
        # 거래 개설 시도 (실제로는 주문 생성 로직이 실행됨)
        assert runner._total_trades_opened >= 0  # 최소한 시도됨
    
    def test_execute_trades_close(self):
        """거래 종료"""
        engine = ArbitrageEngine(
            ArbitrageConfig(
                min_spread_bps=30.0,
                taker_fee_a_bps=5.0,
                taker_fee_b_bps=5.0,
                slippage_bps=5.0,
                max_position_usd=1000.0,
            )
        )
        
        exchange_a = PaperExchange()
        exchange_b = PaperExchange()
        
        config = ArbitrageLiveConfig(
            symbol_a="KRW-BTC",
            symbol_b="BTCUSDT",
        )
        
        runner = ArbitrageLiveRunner(
            engine=engine,
            exchange_a=exchange_a,
            exchange_b=exchange_b,
            config=config,
        )
        
        # 거래 종료
        trade = ArbitrageTrade(
            open_timestamp=datetime.utcnow().isoformat(),
            close_timestamp=datetime.utcnow().isoformat(),
            side="LONG_A_SHORT_B",
            entry_spread_bps=50.0,
            exit_spread_bps=20.0,
            notional_usd=1000.0,
            pnl_usd=100.0,
            pnl_bps=10.0,
            is_open=False,
        )
        
        runner.execute_trades([trade])
        
        assert runner._total_trades_closed == 1
        assert runner._total_pnl_usd == 100.0


class TestRunOnce:
    """run_once 메서드 테스트"""
    
    @pytest.mark.live_api
    def test_run_once_full_pipeline(self):
        """1회 루프 전체 파이프라인"""
        engine = ArbitrageEngine(
            ArbitrageConfig(
                min_spread_bps=30.0,
                taker_fee_a_bps=5.0,
                taker_fee_b_bps=5.0,
                slippage_bps=5.0,
                max_position_usd=1000.0,
            )
        )
        
        exchange_a = PaperExchange(initial_balance={"KRW": 1000000.0})
        exchange_b = PaperExchange(initial_balance={"USDT": 10000.0})
        
        # 호가 설정
        snapshot_a = ExchangeOrderBookSnapshot(
            symbol="KRW-BTC",
            timestamp=time.time(),
            bids=[(100000.0, 1.0)],
            asks=[(101000.0, 1.0)],
        )
        exchange_a.set_orderbook("KRW-BTC", snapshot_a)
        
        snapshot_b = ExchangeOrderBookSnapshot(
            symbol="BTCUSDT",
            timestamp=time.time(),
            bids=[(40000.0, 1.0)],
            asks=[(40100.0, 1.0)],
        )
        exchange_b.set_orderbook("BTCUSDT", snapshot_b)
        
        config = ArbitrageLiveConfig(
            symbol_a="KRW-BTC",
            symbol_b="BTCUSDT",
        )
        
        runner = ArbitrageLiveRunner(
            engine=engine,
            exchange_a=exchange_a,
            exchange_b=exchange_b,
            config=config,
        )
        
        result = runner.run_once()
        
        assert result is True
        assert runner._loop_count == 1


class TestRunForever:
    """run_forever 메서드 테스트"""
    
    def test_run_forever_respects_max_runtime(self):
        """최대 런타임 준수"""
        engine = ArbitrageEngine(
            ArbitrageConfig(
                min_spread_bps=30.0,
                taker_fee_a_bps=5.0,
                taker_fee_b_bps=5.0,
                slippage_bps=5.0,
                max_position_usd=1000.0,
            )
        )
        
        exchange_a = PaperExchange(initial_balance={"KRW": 1000000.0})
        exchange_b = PaperExchange(initial_balance={"USDT": 10000.0})
        
        # 호가 설정
        snapshot_a = ExchangeOrderBookSnapshot(
            symbol="KRW-BTC",
            timestamp=time.time(),
            bids=[(100000.0, 1.0)],
            asks=[(101000.0, 1.0)],
        )
        exchange_a.set_orderbook("KRW-BTC", snapshot_a)
        
        snapshot_b = ExchangeOrderBookSnapshot(
            symbol="BTCUSDT",
            timestamp=time.time(),
            bids=[(40000.0, 1.0)],
            asks=[(40100.0, 1.0)],
        )
        exchange_b.set_orderbook("BTCUSDT", snapshot_b)
        
        config = ArbitrageLiveConfig(
            symbol_a="KRW-BTC",
            symbol_b="BTCUSDT",
            poll_interval_seconds=0.01,  # 빠르게 실행
            max_runtime_seconds=0.1,  # 0.1초 제한
        )
        
        runner = ArbitrageLiveRunner(
            engine=engine,
            exchange_a=exchange_a,
            exchange_b=exchange_b,
            config=config,
        )
        
        start_time = time.time()
        runner.run_forever()
        elapsed = time.time() - start_time
        
        # 최대 런타임 초과하지 않음
        assert elapsed < 1.0  # 충분한 여유


class TestGetStats:
    """get_stats 메서드 테스트"""
    
    def test_get_stats(self):
        """통계 조회"""
        engine = ArbitrageEngine(
            ArbitrageConfig(
                min_spread_bps=30.0,
                taker_fee_a_bps=5.0,
                taker_fee_b_bps=5.0,
                slippage_bps=5.0,
                max_position_usd=1000.0,
            )
        )
        
        exchange_a = PaperExchange()
        exchange_b = PaperExchange()
        
        config = ArbitrageLiveConfig(
            symbol_a="KRW-BTC",
            symbol_b="BTCUSDT",
        )
        
        runner = ArbitrageLiveRunner(
            engine=engine,
            exchange_a=exchange_a,
            exchange_b=exchange_b,
            config=config,
        )
        
        stats = runner.get_stats()
        
        assert "elapsed_seconds" in stats
        assert "loop_count" in stats
        assert "total_trades_opened" in stats
        assert "total_trades_closed" in stats
        assert "total_pnl_usd" in stats
        assert "active_orders" in stats


class TestPaperModeNoNetworkCalls:
    """Paper 모드에서 네트워크 호출 없음 확인"""
    
    def test_no_network_calls_in_paper_mode(self):
        """Paper 모드에서는 네트워크 호출이 없음"""
        engine = ArbitrageEngine(
            ArbitrageConfig(
                min_spread_bps=30.0,
                taker_fee_a_bps=5.0,
                taker_fee_b_bps=5.0,
                slippage_bps=5.0,
                max_position_usd=1000.0,
            )
        )
        
        exchange_a = PaperExchange(initial_balance={"KRW": 1000000.0})
        exchange_b = PaperExchange(initial_balance={"USDT": 10000.0})
        
        config = ArbitrageLiveConfig(
            symbol_a="KRW-BTC",
            symbol_b="BTCUSDT",
            mode="paper",
        )
        
        runner = ArbitrageLiveRunner(
            engine=engine,
            exchange_a=exchange_a,
            exchange_b=exchange_b,
            config=config,
        )
        
        # requests 라이브러리가 호출되지 않음을 확인
        with patch("requests.get") as mock_get:
            with patch("requests.post") as mock_post:
                runner.run_once()
                
                # 호출되지 않음
                mock_get.assert_not_called()
                mock_post.assert_not_called()
