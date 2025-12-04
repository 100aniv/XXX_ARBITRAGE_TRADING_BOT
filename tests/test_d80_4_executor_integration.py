# -*- coding: utf-8 -*-
"""
D80-4: Executor + Fill Model Integration Tests
Executor와 Fill Model 통합 테스트

목적:
    PaperExecutor가 Fill Model을 정상적으로 호출하고,
    ExecutionResult에 Fill Model 결과가 반영되는지 검증.

Author: arbitrage-lite project
Date: 2025-12-04
"""

import pytest
from datetime import datetime
from unittest.mock import Mock

from arbitrage.execution.executor import PaperExecutor, ExecutionResult
from arbitrage.execution.fill_model import SimpleFillModel
from arbitrage.types import PortfolioState, OrderSide
from arbitrage.live_runner import RiskGuard


class MockTrade:
    """Mock ArbitrageTrade for testing"""
    def __init__(
        self,
        trade_id: str,
        symbol: str,
        quantity: float,
        buy_price: float,
        sell_price: float,
        buy_exchange: str = "upbit",
        sell_exchange: str = "binance",
        notional_usd: float = 10000.0,
    ):
        self.trade_id = trade_id
        self.symbol = symbol
        self.quantity = quantity
        self.buy_price = buy_price
        self.sell_price = sell_price
        self.buy_exchange = buy_exchange
        self.sell_exchange = sell_exchange
        self.notional_usd = notional_usd


class TestExecutorFillModelIntegration:
    """Executor + Fill Model 통합 테스트"""
    
    @pytest.fixture
    def portfolio_state(self):
        """PortfolioState mock"""
        state = Mock(spec=PortfolioState)
        state.get_symbol_capital_used = Mock(return_value=0.0)
        state.update_symbol_capital_used = Mock()
        state.update_symbol_position_count = Mock()
        return state
    
    @pytest.fixture
    def risk_guard(self):
        """RiskGuard mock"""
        guard = Mock(spec=RiskGuard)
        guard.check_symbol_capital_limit = Mock(return_value=True)
        guard.check_symbol_position_limit = Mock(return_value=True)
        return guard
    
    def test_executor_without_fill_model(self, portfolio_state, risk_guard):
        """
        테스트 1: Fill Model 없이 Executor 실행 (기존 동작)
        
        조건:
            - enable_fill_model=False (기본값)
        
        기대 결과:
            - 100% 전량 체결
            - 슬리피지 0
            - status = "success"
        """
        executor = PaperExecutor(
            symbol="BTC/USDT",
            portfolio_state=portfolio_state,
            risk_guard=risk_guard,
            enable_fill_model=False,  # 명시적으로 비활성화
        )
        
        trade = MockTrade(
            trade_id="TEST_001",
            symbol="BTC/USDT",
            quantity=10.0,
            buy_price=100000.0,
            sell_price=100200.0,
        )
        
        results = executor.execute_trades([trade])
        
        assert len(results) == 1
        result = results[0]
        
        # 기존 동작 확인
        assert result.status == "success"
        assert result.quantity == 10.0  # 전량 체결
        assert result.buy_price == 100000.0  # 슬리피지 없음
        assert result.sell_price == 100200.0  # 슬리피지 없음
        assert result.buy_slippage_bps == 0.0
        assert result.sell_slippage_bps == 0.0
        assert result.buy_fill_ratio == 1.0
        assert result.sell_fill_ratio == 1.0
        
        # PnL 계산
        expected_pnl = (100200.0 - 100000.0) * 10.0
        assert abs(result.pnl - expected_pnl) < 0.01
    
    def test_executor_with_fill_model_full_fill(self, portfolio_state, risk_guard):
        """
        테스트 2: Fill Model 활성화 - 전량 체결 케이스
        
        조건:
            - enable_fill_model=True
            - 호가 잔량 충분 (factor=2.0 → 20.0 available)
        
        기대 결과:
            - 전량 체결 (quantity = 10.0)
            - 슬리피지 발생 (> 0 bps)
            - status = "success"
        """
        executor = PaperExecutor(
            symbol="BTC/USDT",
            portfolio_state=portfolio_state,
            risk_guard=risk_guard,
            enable_fill_model=True,
            fill_model=SimpleFillModel(
                enable_partial_fill=True,
                enable_slippage=True,
                default_slippage_alpha=0.0001,
            ),
            default_available_volume_factor=2.0,
        )
        
        trade = MockTrade(
            trade_id="TEST_002",
            symbol="BTC/USDT",
            quantity=10.0,
            buy_price=100000.0,
            sell_price=100200.0,
        )
        
        results = executor.execute_trades([trade])
        
        assert len(results) == 1
        result = results[0]
        
        # Fill Model 결과 확인
        assert result.status == "success"
        assert result.quantity == 10.0  # 전량 체결 (호가 충분)
        
        # 슬리피지 발생 확인
        assert result.buy_price > trade.buy_price  # 매수: 가격 상승
        assert result.sell_price < trade.sell_price  # 매도: 가격 하락
        assert result.buy_slippage_bps > 0
        assert result.sell_slippage_bps > 0
        
        # Fill ratio
        assert result.buy_fill_ratio == 1.0
        assert result.sell_fill_ratio == 1.0
        
        # PnL은 슬리피지로 인해 기존보다 감소
        expected_pnl_without_slippage = (100200.0 - 100000.0) * 10.0
        assert result.pnl < expected_pnl_without_slippage
    
    def test_executor_with_fill_model_partial_fill(self, portfolio_state, risk_guard):
        """
        테스트 3: Fill Model 활성화 - 부분 체결 케이스
        
        조건:
            - enable_fill_model=True
            - 호가 잔량 부족 (factor=0.65 → 6.5 available)
        
        기대 결과:
            - 부분 체결 (quantity = 6.5)
            - 슬리피지 발생
            - status = "partial"
        """
        executor = PaperExecutor(
            symbol="BTC/USDT",
            portfolio_state=portfolio_state,
            risk_guard=risk_guard,
            enable_fill_model=True,
            fill_model=SimpleFillModel(
                enable_partial_fill=True,
                enable_slippage=True,
                default_slippage_alpha=0.0001,
            ),
            default_available_volume_factor=0.65,  # 부족
        )
        
        trade = MockTrade(
            trade_id="TEST_003",
            symbol="BTC/USDT",
            quantity=10.0,
            buy_price=100000.0,
            sell_price=100200.0,
        )
        
        results = executor.execute_trades([trade])
        
        assert len(results) == 1
        result = results[0]
        
        # 부분 체결 확인
        assert result.status == "partial"
        assert result.quantity == 6.5  # 부분 체결
        assert result.quantity < trade.quantity
        
        # Fill ratio
        assert abs(result.buy_fill_ratio - 0.65) < 0.01
        assert abs(result.sell_fill_ratio - 1.0) < 0.01  # 매도는 6.5만큼만 주문
        
        # 슬리피지 발생
        assert result.buy_slippage_bps > 0
        assert result.sell_slippage_bps > 0
    
    def test_executor_with_fill_model_no_fill(self, portfolio_state, risk_guard):
        """
        테스트 4: Fill Model 활성화 - 미체결 케이스
        
        조건:
            - enable_fill_model=True
            - 호가 잔량 없음 (factor=0.0 → 0.0 available)
        
        기대 결과:
            - 미체결 (quantity = 0.0)
            - status = "failed"
            - PnL = 0
        """
        executor = PaperExecutor(
            symbol="BTC/USDT",
            portfolio_state=portfolio_state,
            risk_guard=risk_guard,
            enable_fill_model=True,
            fill_model=SimpleFillModel(
                enable_partial_fill=True,
                enable_slippage=True,
                default_slippage_alpha=0.0001,
            ),
            default_available_volume_factor=0.0,  # 없음
        )
        
        trade = MockTrade(
            trade_id="TEST_004",
            symbol="BTC/USDT",
            quantity=10.0,
            buy_price=100000.0,
            sell_price=100200.0,
        )
        
        results = executor.execute_trades([trade])
        
        assert len(results) == 1
        result = results[0]
        
        # 미체결 확인
        assert result.status == "failed"
        assert result.quantity == 0.0
        assert result.pnl == 0.0
        assert result.buy_fill_ratio == 0.0
    
    def test_executor_factory_creates_with_fill_model(self, portfolio_state, risk_guard):
        """
        테스트 5: ExecutorFactory가 Fill Model 파라미터를 정상 전달하는지 확인
        """
        from arbitrage.execution.executor_factory import ExecutorFactory
        from arbitrage.config.settings import FillModelConfig
        
        factory = ExecutorFactory()
        
        fill_model_config = FillModelConfig(
            enable_fill_model=True,
            available_volume_factor=1.5,
        )
        
        executor = factory.create_paper_executor(
            symbol="BTC/USDT",
            portfolio_state=portfolio_state,
            risk_guard=risk_guard,
            fill_model_config=fill_model_config,
        )
        
        assert executor.enable_fill_model is True
        assert executor.fill_model is not None
        assert executor.default_available_volume_factor == 1.5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
