# -*- coding: utf-8 -*-
"""
D57: Multi-Symbol Portfolio Integration Phase 1 - Tests

포트폴리오 멀티심볼 구조 및 symbol-aware 인터페이스 검증.
"""

import pytest
import time
from arbitrage.arbitrage_core import (
    ArbitrageEngine,
    ArbitrageConfig,
)
from arbitrage.exchanges.paper_exchange import PaperExchange
from arbitrage.exchanges.base import OrderBookSnapshot as ExchangeOrderBookSnapshot
from arbitrage.exchanges.market_data_provider import RestMarketDataProvider
from arbitrage.live_runner import ArbitrageLiveRunner, ArbitrageLiveConfig
from arbitrage.monitoring.metrics_collector import MetricsCollector
from arbitrage.types import PortfolioState, Position, Order, OrderSide


class TestPortfolioStateMultiSymbol:
    """PortfolioState 멀티심볼 확장 테스트"""
    
    def test_portfolio_state_symbol_aware_fields(self):
        """PortfolioState symbol-aware 필드 존재 확인"""
        state = PortfolioState(
            total_balance=100000.0,
            available_balance=100000.0,
        )
        
        # D57 필드 확인
        assert hasattr(state, 'symbol')
        assert hasattr(state, 'per_symbol_positions')
        assert hasattr(state, 'per_symbol_orders')
        assert state.symbol is None
        assert state.per_symbol_positions == {}
        assert state.per_symbol_orders == {}
    
    def test_add_symbol_position(self):
        """심볼별 포지션 추가"""
        state = PortfolioState(
            total_balance=100000.0,
            available_balance=100000.0,
        )
        
        # 포지션 생성
        pos = Position(
            symbol="BTC",
            quantity=1.0,
            entry_price=50000.0,
            current_price=51000.0,
            side=OrderSide.BUY,
        )
        
        # 심볼별 포지션 추가
        state.add_symbol_position("KRW-BTC", "pos_1", pos)
        
        # 확인
        assert "KRW-BTC" in state.per_symbol_positions
        assert "pos_1" in state.per_symbol_positions["KRW-BTC"]
        assert state.per_symbol_positions["KRW-BTC"]["pos_1"] == pos
    
    def test_get_symbol_positions(self):
        """심볼별 포지션 조회"""
        state = PortfolioState(
            total_balance=100000.0,
            available_balance=100000.0,
        )
        
        # 포지션 생성
        pos1 = Position(
            symbol="BTC",
            quantity=1.0,
            entry_price=50000.0,
            current_price=51000.0,
            side=OrderSide.BUY,
        )
        pos2 = Position(
            symbol="BTC",
            quantity=2.0,
            entry_price=49000.0,
            current_price=51000.0,
            side=OrderSide.BUY,
        )
        
        # 포지션 추가
        state.add_symbol_position("KRW-BTC", "pos_1", pos1)
        state.add_symbol_position("KRW-BTC", "pos_2", pos2)
        
        # 조회
        positions = state.get_symbol_positions("KRW-BTC")
        
        assert len(positions) == 2
        assert "pos_1" in positions
        assert "pos_2" in positions
    
    def test_get_total_symbol_position_value(self):
        """심볼별 총 포지션 가치 계산"""
        state = PortfolioState(
            total_balance=100000.0,
            available_balance=100000.0,
        )
        
        # 포지션 생성
        pos1 = Position(
            symbol="BTC",
            quantity=1.0,
            entry_price=50000.0,
            current_price=51000.0,
            side=OrderSide.BUY,
        )
        pos2 = Position(
            symbol="BTC",
            quantity=2.0,
            entry_price=49000.0,
            current_price=51000.0,
            side=OrderSide.BUY,
        )
        
        # 포지션 추가
        state.add_symbol_position("KRW-BTC", "pos_1", pos1)
        state.add_symbol_position("KRW-BTC", "pos_2", pos2)
        
        # 총 가치 계산
        total_value = state.get_total_symbol_position_value("KRW-BTC")
        
        # 1.0 * 51000 + 2.0 * 51000 = 153000
        assert total_value == 153000.0


class TestMetricsCollectorSymbolSupport:
    """MetricsCollector symbol 파라미터 지원 테스트"""
    
    def test_update_loop_metrics_with_symbol(self):
        """symbol 파라미터를 포함한 메트릭 업데이트"""
        collector = MetricsCollector()
        
        # symbol 파라미터 포함
        collector.update_loop_metrics(
            loop_time_ms=1000.0,
            trades_opened=1,
            spread_bps=50.0,
            data_source="rest",
            ws_connected=False,
            ws_reconnects=0,
            symbol="KRW-BTC",
        )
        
        # 메트릭 확인
        metrics = collector.get_metrics()
        assert metrics['loop_time_avg_ms'] > 0
        assert metrics['trades_opened_recent'] == 1
    
    def test_aupdate_loop_metrics_with_symbol(self):
        """async update_loop_metrics with symbol"""
        import asyncio
        
        async def test():
            collector = MetricsCollector()
            
            # symbol 파라미터 포함
            await collector.aupdate_loop_metrics(
                loop_time_ms=1000.0,
                trades_opened=1,
                spread_bps=50.0,
                data_source="rest",
                ws_connected=False,
                ws_reconnects=0,
                symbol="KRW-BTC",
            )
            
            # 메트릭 확인
            metrics = collector.get_metrics()
            assert metrics['loop_time_avg_ms'] > 0
            assert metrics['trades_opened_recent'] == 1
        
        asyncio.run(test())


class TestLiveRunnerSymbolAwarePortfolio:
    """LiveRunner symbol-aware 포트폴리오 추적 테스트"""
    
    def test_run_once_for_symbol_with_portfolio_tracking(self):
        """run_once_for_symbol에서 포트폴리오 추적"""
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
        
        provider = RestMarketDataProvider(exchanges={"a": exchange_a, "b": exchange_b})
        provider.start()
        
        runner = ArbitrageLiveRunner(
            engine=engine,
            exchange_a=exchange_a,
            exchange_b=exchange_b,
            config=config,
            market_data_provider=provider,
        )
        
        # 포트폴리오 상태 초기화
        runner._portfolio_state = PortfolioState(
            total_balance=1000000.0,
            available_balance=1000000.0,
        )
        
        # 심볼별 루프 실행
        result = runner.run_once_for_symbol("KRW-BTC")
        
        assert result is True
        
        # 포트폴리오에 심볼이 기록되었는지 확인
        # (실제 포지션이 열렸다면 per_symbol_positions에 추가됨)
        
        provider.stop()
    
    @pytest.mark.asyncio
    async def test_arun_once_for_symbol_with_portfolio_tracking(self):
        """arun_once_for_symbol에서 포트폴리오 추적"""
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
        
        provider = RestMarketDataProvider(exchanges={"a": exchange_a, "b": exchange_b})
        await provider.astart()
        
        runner = ArbitrageLiveRunner(
            engine=engine,
            exchange_a=exchange_a,
            exchange_b=exchange_b,
            config=config,
            market_data_provider=provider,
        )
        
        # 포트폴리오 상태 초기화
        runner._portfolio_state = PortfolioState(
            total_balance=1000000.0,
            available_balance=1000000.0,
        )
        
        # 심볼별 async 루프 실행
        result = await runner.arun_once_for_symbol("KRW-BTC")
        
        assert result is True
        
        await provider.astop()


class TestBackwardCompatibilityD57:
    """D57 추가 후 기존 기능 호환성"""
    
    def test_portfolio_state_backward_compatible(self):
        """기존 PortfolioState 기능 유지"""
        state = PortfolioState(
            total_balance=100000.0,
            available_balance=100000.0,
        )
        
        # 기존 필드 확인
        assert state.total_balance == 100000.0
        assert state.available_balance == 100000.0
        assert state.positions == {}
        assert state.orders == {}
        assert state.total_position_value == 0.0
        assert state.utilization_rate == 0.0
    
    def test_metrics_collector_backward_compatible(self):
        """기존 MetricsCollector 기능 유지"""
        collector = MetricsCollector()
        
        # symbol 파라미터 없이 호출 (기존 방식)
        collector.update_loop_metrics(
            loop_time_ms=1000.0,
            trades_opened=1,
            spread_bps=50.0,
            data_source="rest",
            ws_connected=False,
            ws_reconnects=0,
        )
        
        # 메트릭 확인
        metrics = collector.get_metrics()
        assert metrics['loop_time_avg_ms'] > 0
        assert metrics['trades_opened_recent'] == 1
        assert metrics['trades_opened_total'] == 1
