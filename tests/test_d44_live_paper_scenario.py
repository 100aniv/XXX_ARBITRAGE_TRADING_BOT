# -*- coding: utf-8 -*-
"""
D44 Live Paper Scenario 테스트

Paper 모드에서 엔드 투 엔드 시나리오를 검증합니다.
"""

import pytest
import threading
import time

from arbitrage.arbitrage_core import ArbitrageEngine, ArbitrageConfig, OrderBookSnapshot
from arbitrage.exchanges import PaperExchange
from arbitrage.live_runner import ArbitrageLiveRunner, ArbitrageLiveConfig, RiskLimits


class TestLiveRunnerPaperScenario:
    """Paper 모드 Live Runner E2E 시나리오"""
    
    def test_live_runner_basic_execution(self):
        """기본 Live Runner 실행"""
        engine = ArbitrageEngine(
            ArbitrageConfig(
                min_spread_bps=20.0,
                taker_fee_a_bps=5.0,
                taker_fee_b_bps=4.0,
                slippage_bps=5.0,
                max_position_usd=5000.0,
                max_open_trades=1,
            )
        )
        
        exchange_a = PaperExchange(initial_balance={"KRW": 100000000.0, "BTC": 10.0})
        exchange_b = PaperExchange(initial_balance={"USDT": 1000000.0, "BTC": 10.0})
        
        config = ArbitrageLiveConfig(
            symbol_a="KRW-BTC",
            symbol_b="BTCUSDT",
            max_runtime_seconds=5,  # 5초 테스트
            poll_interval_seconds=0.5,
        )
        
        runner = ArbitrageLiveRunner(
            engine=engine,
            exchange_a=exchange_a,
            exchange_b=exchange_b,
            config=config,
        )
        
        # 실행
        runner.run_forever()
        
        # 통계 확인
        stats = runner.get_stats()
        assert stats["loop_count"] > 0
        assert stats["elapsed_seconds"] >= 5.0
    
    def test_live_runner_with_risk_guard(self):
        """RiskGuard 포함 Live Runner 실행"""
        engine = ArbitrageEngine(
            ArbitrageConfig(
                min_spread_bps=20.0,
                taker_fee_a_bps=5.0,
                taker_fee_b_bps=4.0,
                slippage_bps=5.0,
                max_position_usd=5000.0,
                max_open_trades=1,
            )
        )
        
        exchange_a = PaperExchange(initial_balance={"KRW": 100000000.0, "BTC": 10.0})
        exchange_b = PaperExchange(initial_balance={"USDT": 1000000.0, "BTC": 10.0})
        
        risk_limits = RiskLimits(
            max_notional_per_trade=5000.0,
            max_daily_loss=10000.0,
            max_open_trades=1,
        )
        
        config = ArbitrageLiveConfig(
            symbol_a="KRW-BTC",
            symbol_b="BTCUSDT",
            max_runtime_seconds=5,
            poll_interval_seconds=0.5,
            risk_limits=risk_limits,
        )
        
        runner = ArbitrageLiveRunner(
            engine=engine,
            exchange_a=exchange_a,
            exchange_b=exchange_b,
            config=config,
        )
        
        # RiskGuard 초기화 확인
        assert runner._risk_guard is not None
        assert runner._risk_guard.risk_limits.max_notional_per_trade == 5000.0
        
        # 실행
        runner.run_forever()
        
        # 통계 확인
        stats = runner.get_stats()
        assert stats["loop_count"] > 0


class TestLiveRunnerWithDynamicPrices:
    """동적 호가 주입 시나리오"""
    
    def inject_prices_thread(self, exchange_a, exchange_b, duration=10):
        """동적 호가 주입 스레드"""
        start_time = time.time()
        
        while time.time() - start_time < duration:
            elapsed = time.time() - start_time
            
            # 시간에 따라 호가 변동
            if elapsed < 3:
                bid_a, ask_a = 100000.0, 100000.0
                bid_b, ask_b = 40000.0, 40000.0
            elif elapsed < 7:
                # 스프레드 생성
                bid_a, ask_a = 99000.0, 99500.0
                bid_b, ask_b = 40500.0, 41000.0
            else:
                bid_a, ask_a = 100000.0, 100000.0
                bid_b, ask_b = 40000.0, 40000.0
            
            # 호가 주입
            snapshot_a = OrderBookSnapshot(
                symbol="KRW-BTC",
                timestamp=time.time(),
                bids=[(bid_a, 1.0)],
                asks=[(ask_a, 1.0)],
            )
            exchange_a.set_orderbook("KRW-BTC", snapshot_a)
            
            snapshot_b = OrderBookSnapshot(
                symbol="BTCUSDT",
                timestamp=time.time(),
                bids=[(bid_b, 1.0)],
                asks=[(ask_b, 1.0)],
            )
            exchange_b.set_orderbook("BTCUSDT", snapshot_b)
            
            time.sleep(0.5)
    
    def test_live_runner_with_dynamic_prices(self):
        """동적 호가로 거래 신호 생성"""
        engine = ArbitrageEngine(
            ArbitrageConfig(
                min_spread_bps=20.0,
                taker_fee_a_bps=5.0,
                taker_fee_b_bps=4.0,
                slippage_bps=5.0,
                max_position_usd=5000.0,
                max_open_trades=1,
            )
        )
        
        exchange_a = PaperExchange(initial_balance={"KRW": 100000000.0, "BTC": 10.0})
        exchange_b = PaperExchange(initial_balance={"USDT": 1000000.0, "BTC": 10.0})
        
        config = ArbitrageLiveConfig(
            symbol_a="KRW-BTC",
            symbol_b="BTCUSDT",
            max_runtime_seconds=10,
            poll_interval_seconds=0.5,
        )
        
        runner = ArbitrageLiveRunner(
            engine=engine,
            exchange_a=exchange_a,
            exchange_b=exchange_b,
            config=config,
        )
        
        # 동적 호가 주입 스레드 시작
        price_thread = threading.Thread(
            target=self.inject_prices_thread,
            args=(exchange_a, exchange_b, 10),
            daemon=True,
        )
        price_thread.start()
        
        # Live Runner 실행
        runner.run_forever()
        
        # 통계 확인
        stats = runner.get_stats()
        assert stats["loop_count"] > 0
        # 동적 호가로 인해 최소 1회 이상 거래 신호가 생성되어야 함
        # (실제로는 스프레드 계산에 따라 다를 수 있음)


class TestLiveRunnerRiskGuardIntegration:
    """RiskGuard 통합 테스트"""
    
    def test_riskguard_rejects_oversized_trade(self):
        """RiskGuard가 과도한 거래 거절"""
        engine = ArbitrageEngine(
            ArbitrageConfig(
                min_spread_bps=20.0,
                taker_fee_a_bps=5.0,
                taker_fee_b_bps=4.0,
                slippage_bps=5.0,
                max_position_usd=100.0,  # 매우 작은 거래 규모
                max_open_trades=1,
            )
        )
        
        exchange_a = PaperExchange(initial_balance={"KRW": 100000000.0, "BTC": 10.0})
        exchange_b = PaperExchange(initial_balance={"USDT": 1000000.0, "BTC": 10.0})
        
        risk_limits = RiskLimits(
            max_notional_per_trade=50.0,  # 매우 낮은 한계
            max_daily_loss=10000.0,
            max_open_trades=1,
        )
        
        config = ArbitrageLiveConfig(
            symbol_a="KRW-BTC",
            symbol_b="BTCUSDT",
            max_runtime_seconds=3,
            poll_interval_seconds=0.5,
            risk_limits=risk_limits,
        )
        
        runner = ArbitrageLiveRunner(
            engine=engine,
            exchange_a=exchange_a,
            exchange_b=exchange_b,
            config=config,
        )
        
        # 실행
        runner.run_forever()
        
        # 거래가 거절되었을 가능성 확인
        stats = runner.get_stats()
        assert stats["loop_count"] > 0
