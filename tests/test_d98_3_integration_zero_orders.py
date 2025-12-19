# -*- coding: utf-8 -*-
"""
D98-3: Integration Tests - Zero Live Orders Guarantee

Objective: Prove that the complete Executor + LiveAPI stack produces ZERO real orders
when READ_ONLY_ENFORCED=true, using full component integration.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from arbitrage.execution.executor import LiveExecutor, ExecutionResult
from arbitrage.config.readonly_guard import get_readonly_guard, set_readonly_mode, ReadOnlyError
from arbitrage.types import PortfolioState
from arbitrage.live_runner import RiskGuard


@pytest.fixture
def mock_trade():
    """Mock ArbitrageTrade"""
    trade = Mock()
    trade.trade_id = "integration_trade_001"
    trade.symbol = "BTC-KRW"
    trade.buy_exchange = "upbit"
    trade.sell_exchange = "binance"
    trade.quantity = 0.01
    trade.buy_price = 50000000.0
    trade.sell_price = 51000000.0
    trade.notional_usd = 500.0
    return trade


@pytest.fixture
def mock_portfolio():
    """Mock PortfolioState"""
    portfolio = Mock(spec=PortfolioState)
    portfolio.get_position = Mock(return_value=None)
    portfolio.update_position = Mock()
    portfolio.get_symbol_capital_used = Mock(return_value=0.0)
    portfolio.update_symbol_capital_used = Mock()
    return portfolio


@pytest.fixture
def mock_risk_guard():
    """Mock RiskGuard that always allows"""
    risk_guard = Mock(spec=RiskGuard)
    risk_guard.check_symbol_capital_limit = Mock(return_value=True)
    risk_guard.check_symbol_position_limit = Mock(return_value=True)
    return risk_guard


class TestLiveExecutorIntegrationZeroOrders:
    """D98-3: Full-stack Integration Tests"""
    
    def test_full_stack_zero_api_calls_when_readonly_upbit_only(
        self, mock_trade, mock_portfolio, mock_risk_guard
    ):
        """
        [INTEGRATION] Upbit-only 거래 시 READ_ONLY=true → API 호출 0회
        
        Components:
        - LiveExecutor
        - UpbitLiveAPI
        - ReadOnlyGuard (Executor + API level)
        
        Expected:
        - ReadOnlyError at Executor level (primary defense)
        - NO HTTP requests (verified by mock spy)
        """
        from arbitrage.upbit_live import UpbitLiveAPI
        
        # Arrange
        set_readonly_mode(True)
        
        config = {"api_key": "dummy_upbit_key", "api_secret": "dummy_secret"}
        upbit_api = UpbitLiveAPI(config)
        
        # Spy on place_order (shouldn't be called due to Executor block)
        with patch.object(upbit_api, 'place_order', wraps=upbit_api.place_order) as spy:
            executor = LiveExecutor(
                symbol="BTC-KRW",
                portfolio_state=mock_portfolio,
                risk_guard=mock_risk_guard,
                upbit_api=upbit_api,
                binance_api=None,
                dry_run=False
            )
            
            mock_trade.buy_exchange = "upbit"
            mock_trade.sell_exchange = "upbit"
            trades = [mock_trade]
            
            # Act & Assert
            with pytest.raises(ReadOnlyError) as exc_info:
                executor.execute_trades(trades)
            
            # Verify Executor-level block
            assert "D98-3_EXECUTOR_GUARD" in str(exc_info.value)
            
            # Verify ZERO API calls (primary defense blocked before API)
            spy.assert_not_called()
        
        print("[D98-3_INTEGRATION_PASS] Upbit-only: 0 API calls with READ_ONLY=true")
    
    def test_full_stack_zero_api_calls_when_readonly_binance_only(
        self, mock_trade, mock_portfolio, mock_risk_guard
    ):
        """
        [INTEGRATION] Binance-only 거래 시 READ_ONLY=true → API 호출 0회
        
        Components:
        - LiveExecutor
        - BinanceLiveAPI
        - ReadOnlyGuard (Executor + API level)
        
        Expected:
        - ReadOnlyError at Executor level
        - NO HTTP requests
        """
        from arbitrage.binance_live import BinanceLiveAPI
        
        # Arrange
        set_readonly_mode(True)
        
        config = {"api_key": "dummy_binance_key", "api_secret": "dummy_secret"}
        binance_api = BinanceLiveAPI(config)
        
        with patch.object(binance_api, 'place_order', wraps=binance_api.place_order) as spy:
            executor = LiveExecutor(
                symbol="BTC-USDT",
                portfolio_state=mock_portfolio,
                risk_guard=mock_risk_guard,
                upbit_api=None,
                binance_api=binance_api,
                dry_run=False
            )
            
            mock_trade.buy_exchange = "binance"
            mock_trade.sell_exchange = "binance"
            mock_trade.symbol = "BTC-USDT"
            trades = [mock_trade]
            
            # Act & Assert
            with pytest.raises(ReadOnlyError):
                executor.execute_trades(trades)
            
            # Verify ZERO API calls
            spy.assert_not_called()
        
        print("[D98-3_INTEGRATION_PASS] Binance-only: 0 API calls with READ_ONLY=true")
    
    def test_full_stack_zero_api_calls_cross_exchange(
        self, mock_trade, mock_portfolio, mock_risk_guard
    ):
        """
        [INTEGRATION] 교차 거래소 주문 시 READ_ONLY=true → 양쪽 모두 API 호출 0회
        
        Components:
        - LiveExecutor
        - UpbitLiveAPI + BinanceLiveAPI
        - ReadOnlyGuard (multi-layer defense)
        
        Expected:
        - ReadOnlyError at Executor level (blocks before ANY API call)
        - Upbit API calls: 0
        - Binance API calls: 0
        """
        from arbitrage.upbit_live import UpbitLiveAPI
        from arbitrage.binance_live import BinanceLiveAPI
        
        # Arrange
        set_readonly_mode(True)
        
        upbit_config = {"api_key": "dummy_upbit_key", "api_secret": "dummy_secret"}
        binance_config = {"api_key": "dummy_binance_key", "api_secret": "dummy_secret"}
        
        upbit_api = UpbitLiveAPI(upbit_config)
        binance_api = BinanceLiveAPI(binance_config)
        
        with patch.object(upbit_api, 'place_order', wraps=upbit_api.place_order) as upbit_spy, \
             patch.object(binance_api, 'place_order', wraps=binance_api.place_order) as binance_spy:
            
            executor = LiveExecutor(
                symbol="BTC-KRW",
                portfolio_state=mock_portfolio,
                risk_guard=mock_risk_guard,
                upbit_api=upbit_api,
                binance_api=binance_api,
                dry_run=False
            )
            
            # Cross-exchange arbitrage (buy Upbit, sell Binance)
            mock_trade.buy_exchange = "upbit"
            mock_trade.sell_exchange = "binance"
            trades = [mock_trade]
            
            # Act & Assert
            with pytest.raises(ReadOnlyError):
                executor.execute_trades(trades)
            
            # Verify ZERO API calls on BOTH exchanges
            upbit_spy.assert_not_called()
            binance_spy.assert_not_called()
        
        print("[D98-3_INTEGRATION_PASS] Cross-exchange: 0 API calls on both sides")
    
    def test_defense_in_depth_api_level_fallback(
        self, mock_trade, mock_portfolio, mock_risk_guard
    ):
        """
        [DEFENSE-IN-DEPTH] Executor 우회 시나리오에서 API 레벨 데코레이터 차단
        
        Scenario: 만약 Executor guard가 우회되더라도, API 레벨에서 차단
        
        Expected:
        - place_order() 호출 시 ReadOnlyError (API decorator)
        - HTTP request 0회
        """
        from arbitrage.upbit_live import UpbitLiveAPI
        from arbitrage.live_api import OrderRequest
        from arbitrage.types import OrderSide
        
        # Arrange
        set_readonly_mode(True)
        
        config = {"api_key": "dummy_key", "api_secret": "dummy_secret"}
        api = UpbitLiveAPI(config)
        
        # Simulate direct API call (bypass Executor)
        order = OrderRequest(
            symbol="KRW-BTC",
            side=OrderSide.BUY,
            quantity=0.01,
            price=50000000.0,
            order_type="LIMIT"
        )
        
        # Mock HTTP layer to verify it's never reached
        with patch('arbitrage.upbit_live.requests.post') as http_mock:
            # Act & Assert
            with pytest.raises(ReadOnlyError):
                api.place_order(order)
            
            # Verify decorator blocked BEFORE HTTP layer
            http_mock.assert_not_called()
        
        print("[D98-3_INTEGRATION_PASS] Defense-in-depth: API decorator blocked bypass attempt")
    
    def test_readonly_false_with_dry_run_safe_execution(
        self, mock_trade, mock_portfolio, mock_risk_guard
    ):
        """
        [SAFE MODE] READ_ONLY=false + dry_run=true → 실행 허용하되 실제 주문 없음
        
        Expected:
        - ReadOnlyError 발생 안 함 (READ_ONLY=false)
        - API 호출 0회 (dry_run=true가 차단)
        """
        from arbitrage.upbit_live import UpbitLiveAPI
        
        # Arrange
        set_readonly_mode(False)
        
        config = {"api_key": "dummy_key", "api_secret": "dummy_secret"}
        upbit_api = UpbitLiveAPI(config)
        
        with patch.object(upbit_api, 'place_order', wraps=upbit_api.place_order) as spy:
            executor = LiveExecutor(
                symbol="BTC-KRW",
                portfolio_state=mock_portfolio,
                risk_guard=mock_risk_guard,
                upbit_api=upbit_api,
                binance_api=None,
                dry_run=True  # dry_run으로 안전 보장
            )
            
            mock_trade.buy_exchange = "upbit"
            mock_trade.sell_exchange = "upbit"
            trades = [mock_trade]
            
            # Act
            results = executor.execute_trades(trades)
            
            # Assert
            assert len(results) == 1
            
            # Verify dry_run prevented API calls
            spy.assert_not_called()
        
        print("[D98-3_INTEGRATION_PASS] Safe mode: dry_run prevented real orders")


class TestMultiTradeStressTest:
    """D98-3: Stress test with multiple trades"""
    
    def test_100_trades_all_blocked_single_gate(
        self, mock_trade, mock_portfolio, mock_risk_guard
    ):
        """
        [STRESS TEST] 100개 거래 시도 시 단일 게이트에서 효율적 차단
        
        Expected:
        - ReadOnlyError 1회 발생 (execute_trades 진입 시점)
        - API 호출 0회 (개별 거래 처리 전 차단)
        - 효율적 차단 (O(1) 시간 복잡도)
        """
        from arbitrage.upbit_live import UpbitLiveAPI
        from arbitrage.binance_live import BinanceLiveAPI
        
        # Arrange
        set_readonly_mode(True)
        
        upbit_api = UpbitLiveAPI({"api_key": "key", "api_secret": "secret"})
        binance_api = BinanceLiveAPI({"api_key": "key", "api_secret": "secret"})
        
        with patch.object(upbit_api, 'place_order') as upbit_spy, \
             patch.object(binance_api, 'place_order') as binance_spy:
            
            executor = LiveExecutor(
                symbol="BTC-KRW",
                portfolio_state=mock_portfolio,
                risk_guard=mock_risk_guard,
                upbit_api=upbit_api,
                binance_api=binance_api,
                dry_run=False
            )
            
            # 100개 거래 시도
            trades = [mock_trade for _ in range(100)]
            
            # Act & Assert
            with pytest.raises(ReadOnlyError):
                executor.execute_trades(trades)
            
            # Verify ZERO API calls (efficient single-gate blocking)
            assert upbit_spy.call_count == 0
            assert binance_spy.call_count == 0
        
        print("[D98-3_STRESS_TEST_PASS] 100 trades blocked at O(1) single gate")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
