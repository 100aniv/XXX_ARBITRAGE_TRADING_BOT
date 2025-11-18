# -*- coding: utf-8 -*-
"""
D64: Live Execution Integration Tests

LiveExecutor 및 실제 주문 실행 경로 테스트.
"""

import pytest
from datetime import datetime
from unittest.mock import Mock, MagicMock, patch

from arbitrage.execution import LiveExecutor, ExecutorFactory
from arbitrage.types import PortfolioState, OrderSide
from arbitrage.live_runner import RiskGuard, RiskLimits


class TestLiveExecutor:
    """LiveExecutor 테스트"""
    
    @pytest.fixture
    def portfolio_state(self):
        """포트폴리오 상태 fixture"""
        return PortfolioState(total_balance=100000.0, available_balance=100000.0)
    
    @pytest.fixture
    def risk_guard(self):
        """리스크 가드 fixture"""
        limits = RiskLimits(
            max_notional_per_trade=10000.0,
            max_daily_loss=50000.0,
            max_open_trades=5,
        )
        return RiskGuard(limits)
    
    @pytest.fixture
    def live_executor(self, portfolio_state, risk_guard):
        """LiveExecutor fixture (dry_run=True)"""
        return LiveExecutor(
            symbol="KRW-BTC",
            portfolio_state=portfolio_state,
            risk_guard=risk_guard,
            dry_run=True,
        )
    
    def test_live_executor_initialization(self, portfolio_state, risk_guard):
        """LiveExecutor 초기화 테스트"""
        executor = LiveExecutor(
            symbol="KRW-BTC",
            portfolio_state=portfolio_state,
            risk_guard=risk_guard,
            dry_run=True,
        )
        
        assert executor.symbol == "KRW-BTC"
        assert executor.dry_run is True
        assert executor.execution_count == 0
        assert executor.total_pnl == 0.0
        assert len(executor.positions) == 0
    
    def test_live_executor_with_api_clients(self, portfolio_state, risk_guard):
        """API 클라이언트 포함 초기화"""
        upbit_api = Mock()
        binance_api = Mock()
        
        executor = LiveExecutor(
            symbol="KRW-BTC",
            portfolio_state=portfolio_state,
            risk_guard=risk_guard,
            upbit_api=upbit_api,
            binance_api=binance_api,
            dry_run=False,
        )
        
        assert executor.upbit_api is upbit_api
        assert executor.binance_api is binance_api
        assert executor.dry_run is False
    
    def test_execute_trades_dry_run(self, live_executor):
        """Dry-run 모드에서 거래 실행"""
        # Mock trade
        trade = Mock()
        trade.trade_id = "TRADE_001"
        trade.symbol = "KRW-BTC"
        trade.quantity = 0.01
        trade.buy_price = 100000.0
        trade.sell_price = 101000.0
        trade.notional_usd = 1000.0
        trade.buy_exchange = "upbit"
        trade.sell_exchange = "binance"
        
        results = live_executor.execute_trades([trade])
        
        assert len(results) == 1
        assert results[0].status == "success"
        assert results[0].symbol == "KRW-BTC"
        assert results[0].quantity == 0.01
        assert results[0].pnl == 10.0  # (101000 - 100000) * 0.01
    
    def test_execute_trades_multiple(self, live_executor):
        """여러 거래 실행"""
        trades = []
        for i in range(3):
            trade = Mock()
            trade.trade_id = f"TRADE_{i:03d}"
            trade.symbol = "KRW-BTC"
            trade.quantity = 0.01
            trade.buy_price = 100000.0 + i * 1000
            trade.sell_price = 101000.0 + i * 1000
            trade.notional_usd = 1000.0
            trade.buy_exchange = "upbit"
            trade.sell_exchange = "binance"
            trades.append(trade)
        
        results = live_executor.execute_trades(trades)
        
        assert len(results) == 3
        assert all(r.status == "success" for r in results)
        assert live_executor.execution_count == 3
        assert live_executor.total_pnl == 30.0  # 3 * 10.0
    
    def test_get_positions(self, live_executor):
        """포지션 조회"""
        trade = Mock()
        trade.trade_id = "TRADE_001"
        trade.symbol = "KRW-BTC"
        trade.quantity = 0.01
        trade.buy_price = 100000.0
        trade.sell_price = 101000.0
        trade.notional_usd = 1000.0
        trade.buy_exchange = "upbit"
        trade.sell_exchange = "binance"
        
        live_executor.execute_trades([trade])
        
        positions = live_executor.get_positions()
        assert len(positions) == 1
        assert "POS_KRW-BTC_0" in positions
    
    def test_get_pnl(self, live_executor):
        """PnL 조회"""
        trade = Mock()
        trade.trade_id = "TRADE_001"
        trade.symbol = "KRW-BTC"
        trade.quantity = 0.01
        trade.buy_price = 100000.0
        trade.sell_price = 101000.0
        trade.notional_usd = 1000.0
        trade.buy_exchange = "upbit"
        trade.sell_exchange = "binance"
        
        live_executor.execute_trades([trade])
        
        pnl = live_executor.get_pnl()
        assert pnl == 10.0
    
    def test_close_position(self, live_executor):
        """포지션 청산"""
        trade = Mock()
        trade.trade_id = "TRADE_001"
        trade.symbol = "KRW-BTC"
        trade.quantity = 0.01
        trade.buy_price = 100000.0
        trade.sell_price = 101000.0
        trade.notional_usd = 1000.0
        trade.buy_exchange = "upbit"
        trade.sell_exchange = "binance"
        
        live_executor.execute_trades([trade])
        
        positions = live_executor.get_positions()
        position_id = list(positions.keys())[0]
        
        result = live_executor.close_position(position_id)
        
        assert result is not None
        assert result.status == "success"
        assert len(live_executor.get_positions()) == 0
    
    def test_close_nonexistent_position(self, live_executor):
        """존재하지 않는 포지션 청산"""
        result = live_executor.close_position("NONEXISTENT")
        
        assert result is None


class TestExecutorFactory:
    """ExecutorFactory 테스트"""
    
    @pytest.fixture
    def portfolio_state(self):
        """포트폴리오 상태 fixture"""
        return PortfolioState(total_balance=100000.0, available_balance=100000.0)
    
    @pytest.fixture
    def risk_guard(self):
        """리스크 가드 fixture"""
        limits = RiskLimits(
            max_notional_per_trade=10000.0,
            max_daily_loss=50000.0,
            max_open_trades=5,
        )
        return RiskGuard(limits)
    
    @pytest.fixture
    def factory(self):
        """ExecutorFactory fixture"""
        return ExecutorFactory()
    
    def test_factory_initialization(self, factory):
        """Factory 초기화"""
        assert len(factory.executors) == 0
    
    def test_create_paper_executor(self, factory, portfolio_state, risk_guard):
        """PaperExecutor 생성"""
        executor = factory.create_paper_executor(
            symbol="KRW-BTC",
            portfolio_state=portfolio_state,
            risk_guard=risk_guard,
        )
        
        assert executor is not None
        assert executor.symbol == "KRW-BTC"
        assert "KRW-BTC" in factory.executors
    
    def test_create_live_executor(self, factory, portfolio_state, risk_guard):
        """LiveExecutor 생성"""
        executor = factory.create_live_executor(
            symbol="KRW-BTC",
            portfolio_state=portfolio_state,
            risk_guard=risk_guard,
            dry_run=True,
        )
        
        assert executor is not None
        assert executor.symbol == "KRW-BTC"
        assert executor.dry_run is True
        assert "KRW-BTC" in factory.executors
    
    def test_create_live_executor_with_apis(self, factory, portfolio_state, risk_guard):
        """API 클라이언트 포함 LiveExecutor 생성"""
        upbit_api = Mock()
        binance_api = Mock()
        
        executor = factory.create_live_executor(
            symbol="KRW-BTC",
            portfolio_state=portfolio_state,
            risk_guard=risk_guard,
            upbit_api=upbit_api,
            binance_api=binance_api,
            dry_run=False,
        )
        
        assert executor.upbit_api is upbit_api
        assert executor.binance_api is binance_api
        assert executor.dry_run is False
    
    def test_get_executor(self, factory, portfolio_state, risk_guard):
        """Executor 조회"""
        factory.create_paper_executor(
            symbol="KRW-BTC",
            portfolio_state=portfolio_state,
            risk_guard=risk_guard,
        )
        
        executor = factory.get_executor("KRW-BTC")
        assert executor is not None
        assert executor.symbol == "KRW-BTC"
    
    def test_get_all_executors(self, factory, portfolio_state, risk_guard):
        """모든 Executor 조회"""
        factory.create_paper_executor(
            symbol="KRW-BTC",
            portfolio_state=portfolio_state,
            risk_guard=risk_guard,
        )
        factory.create_live_executor(
            symbol="KRW-ETH",
            portfolio_state=portfolio_state,
            risk_guard=risk_guard,
            dry_run=True,
        )
        
        executors = factory.get_all_executors()
        assert len(executors) == 2
        assert "KRW-BTC" in executors
        assert "KRW-ETH" in executors
    
    def test_remove_executor(self, factory, portfolio_state, risk_guard):
        """Executor 제거"""
        factory.create_paper_executor(
            symbol="KRW-BTC",
            portfolio_state=portfolio_state,
            risk_guard=risk_guard,
        )
        
        result = factory.remove_executor("KRW-BTC")
        assert result is True
        assert "KRW-BTC" not in factory.executors
    
    def test_remove_nonexistent_executor(self, factory):
        """존재하지 않는 Executor 제거"""
        result = factory.remove_executor("NONEXISTENT")
        assert result is False


class TestLiveExecutorBackwardCompatibility:
    """LiveExecutor 백워드 호환성 테스트"""
    
    @pytest.fixture
    def portfolio_state(self):
        """포트폴리오 상태 fixture"""
        return PortfolioState(total_balance=100000.0, available_balance=100000.0)
    
    @pytest.fixture
    def risk_guard(self):
        """리스크 가드 fixture"""
        limits = RiskLimits(
            max_notional_per_trade=10000.0,
            max_daily_loss=50000.0,
            max_open_trades=5,
        )
        return RiskGuard(limits)
    
    def test_live_executor_implements_base_executor(self, portfolio_state, risk_guard):
        """LiveExecutor가 BaseExecutor 인터페이스 구현"""
        from arbitrage.execution import BaseExecutor
        
        executor = LiveExecutor(
            symbol="KRW-BTC",
            portfolio_state=portfolio_state,
            risk_guard=risk_guard,
            dry_run=True,
        )
        
        assert isinstance(executor, BaseExecutor)
        assert hasattr(executor, "execute_trades")
        assert hasattr(executor, "get_positions")
        assert hasattr(executor, "get_pnl")
        assert hasattr(executor, "close_position")
    
    def test_paper_and_live_executor_same_interface(self, portfolio_state, risk_guard):
        """PaperExecutor와 LiveExecutor가 같은 핵심 메서드 제공"""
        from arbitrage.execution import PaperExecutor
        
        paper_executor = PaperExecutor(
            symbol="KRW-BTC",
            portfolio_state=portfolio_state,
            risk_guard=risk_guard,
        )
        
        live_executor = LiveExecutor(
            symbol="KRW-BTC",
            portfolio_state=portfolio_state,
            risk_guard=risk_guard,
            dry_run=True,
        )
        
        # 핵심 메서드 보유 확인
        core_methods = ["execute_trades", "get_positions", "get_pnl", "close_position"]
        for method in core_methods:
            assert hasattr(paper_executor, method), f"PaperExecutor missing {method}"
            assert hasattr(live_executor, method), f"LiveExecutor missing {method}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
