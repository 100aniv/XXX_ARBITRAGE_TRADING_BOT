# -*- coding: utf-8 -*-
"""
D98-3: LiveExecutor ReadOnly Guard Unit Tests

Objective: Prove that LiveExecutor.execute_trades() blocks all live order execution
when READ_ONLY_ENFORCED=true, with ZERO API calls verified by mock spies.
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
    """Mock ArbitrageTrade object"""
    trade = Mock()
    trade.trade_id = "test_trade_001"
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


@pytest.fixture
def mock_upbit_api():
    """Mock UpbitLiveAPI"""
    api = Mock()
    api.create_order = Mock(return_value={"uuid": "upbit_order_123"})
    api.cancel_order = Mock(return_value=True)
    return api


@pytest.fixture
def mock_binance_api():
    """Mock BinanceLiveAPI"""
    api = Mock()
    api.create_order = Mock(return_value={"orderId": "binance_order_456"})
    api.cancel_order = Mock(return_value=True)
    return api


class TestLiveExecutorReadOnlyGuard:
    """D98-3: LiveExecutor ReadOnly Guard Tests"""
    
    def test_live_executor_blocks_when_readonly_true(
        self, mock_trade, mock_portfolio, mock_risk_guard, mock_upbit_api, mock_binance_api
    ):
        """
        [CRITICAL] READ_ONLY=true 시 LiveExecutor.execute_trades() 호출 차단
        
        Expected:
        - ReadOnlyError 발생
        - upbit_api.create_order 호출 0회
        - binance_api.create_order 호출 0회
        """
        # Arrange
        set_readonly_mode(True)
        
        executor = LiveExecutor(
            symbol="BTC-KRW",
            portfolio_state=mock_portfolio,
            risk_guard=mock_risk_guard,
            upbit_api=mock_upbit_api,
            binance_api=mock_binance_api,
            dry_run=False  # dry_run=False이지만 ReadOnlyGuard가 차단해야 함
        )
        
        trades = [mock_trade]
        
        # Act & Assert
        with pytest.raises(ReadOnlyError) as exc_info:
            executor.execute_trades(trades)
        
        # Verify error message
        assert "D98-3_EXECUTOR_GUARD" in str(exc_info.value)
        assert "READ_ONLY_ENFORCED=true" in str(exc_info.value)
        
        # Verify ZERO API calls
        mock_upbit_api.create_order.assert_not_called()
        mock_binance_api.create_order.assert_not_called()
        mock_upbit_api.cancel_order.assert_not_called()
        mock_binance_api.cancel_order.assert_not_called()
        
        print("[D98-3_TEST_PASS] LiveExecutor blocked with READ_ONLY=true, API calls=0")
    
    def test_live_executor_allows_when_readonly_false_dry_run_true(
        self, mock_trade, mock_portfolio, mock_risk_guard, mock_upbit_api, mock_binance_api
    ):
        """
        [SAFE] READ_ONLY=false + dry_run=true 시 실행 허용 (단, 실제 주문 없음)
        
        Expected:
        - ReadOnlyError 발생 안 함
        - 실제 API 호출 없음 (dry_run 모드)
        """
        # Arrange
        set_readonly_mode(False)
        
        executor = LiveExecutor(
            symbol="BTC-KRW",
            portfolio_state=mock_portfolio,
            risk_guard=mock_risk_guard,
            upbit_api=mock_upbit_api,
            binance_api=mock_binance_api,
            dry_run=True  # dry_run으로 안전 보장
        )
        
        trades = [mock_trade]
        
        # Act
        results = executor.execute_trades(trades)
        
        # Assert
        assert len(results) == 1
        assert results[0].symbol == "BTC-KRW"
        
        # Verify dry_run prevented real API calls
        mock_upbit_api.create_order.assert_not_called()
        mock_binance_api.create_order.assert_not_called()
        
        print("[D98-3_TEST_PASS] LiveExecutor allowed with READ_ONLY=false + dry_run=true")
    
    def test_readonly_guard_precedence_over_dry_run(
        self, mock_trade, mock_portfolio, mock_risk_guard, mock_upbit_api, mock_binance_api
    ):
        """
        [CRITICAL] ReadOnlyGuard가 dry_run보다 우선 차단
        
        Expected:
        - READ_ONLY=true, dry_run=False 시 ReadOnlyError 발생
        - API 호출 0회 (ReadOnlyGuard가 먼저 차단)
        """
        # Arrange
        set_readonly_mode(True)
        
        executor = LiveExecutor(
            symbol="BTC-KRW",
            portfolio_state=mock_portfolio,
            risk_guard=mock_risk_guard,
            upbit_api=mock_upbit_api,
            binance_api=mock_binance_api,
            dry_run=False  # dry_run=False이지만 ReadOnlyGuard가 우선
        )
        
        trades = [mock_trade]
        
        # Act & Assert
        with pytest.raises(ReadOnlyError):
            executor.execute_trades(trades)
        
        # Verify ZERO API calls (ReadOnlyGuard blocked before dry_run check)
        mock_upbit_api.create_order.assert_not_called()
        mock_binance_api.create_order.assert_not_called()
        
        print("[D98-3_TEST_PASS] ReadOnlyGuard precedence confirmed")
    
    def test_multiple_trades_all_blocked_when_readonly_true(
        self, mock_trade, mock_portfolio, mock_risk_guard, mock_upbit_api, mock_binance_api
    ):
        """
        [CRITICAL] 여러 거래 시도 시 단일 게이트에서 모두 차단
        
        Expected:
        - ReadOnlyError 발생 (execute_trades 진입 시점)
        - 개별 거래 처리 전 차단 (효율적)
        """
        # Arrange
        set_readonly_mode(True)
        
        executor = LiveExecutor(
            symbol="BTC-KRW",
            portfolio_state=mock_portfolio,
            risk_guard=mock_risk_guard,
            upbit_api=mock_upbit_api,
            binance_api=mock_binance_api,
            dry_run=False
        )
        
        # 10개 거래 시도
        trades = [mock_trade for _ in range(10)]
        
        # Act & Assert
        with pytest.raises(ReadOnlyError):
            executor.execute_trades(trades)
        
        # Verify ZERO API calls (blocked at gate, not per-trade)
        assert mock_upbit_api.create_order.call_count == 0
        assert mock_binance_api.create_order.call_count == 0
        
        print("[D98-3_TEST_PASS] Multiple trades blocked at single gate")


class TestUpbitLiveAPIReadOnlyGuard:
    """D98-3: UpbitLiveAPI Defense-in-depth Tests"""
    
    def test_upbit_live_api_place_order_blocks_when_readonly_true(self):
        """
        [DEFENSE-IN-DEPTH] UpbitLiveAPI.place_order 데코레이터 차단
        
        Expected:
        - @enforce_readonly 데코레이터가 차단
        - ReadOnlyError 발생
        """
        from arbitrage.upbit_live import UpbitLiveAPI
        from arbitrage.live_api import OrderRequest
        from arbitrage.types import OrderSide
        
        # Arrange
        set_readonly_mode(True)
        
        config = {
            "api_key": "dummy_key",
            "api_secret": "dummy_secret"
        }
        api = UpbitLiveAPI(config)
        
        order = OrderRequest(
            symbol="KRW-BTC",
            side=OrderSide.BUY,
            quantity=0.01,
            price=50000000.0,
            order_type="LIMIT"
        )
        
        # Act & Assert
        with pytest.raises(ReadOnlyError) as exc_info:
            api.place_order(order)
        
        assert "READ_ONLY" in str(exc_info.value).upper()
        print("[D98-3_TEST_PASS] UpbitLiveAPI.place_order blocked by decorator")
    
    def test_upbit_live_api_cancel_order_blocks_when_readonly_true(self):
        """
        [DEFENSE-IN-DEPTH] UpbitLiveAPI.cancel_order 데코레이터 차단
        
        Expected:
        - @enforce_readonly 데코레이터가 차단
        - ReadOnlyError 발생
        """
        from arbitrage.upbit_live import UpbitLiveAPI
        
        # Arrange
        set_readonly_mode(True)
        
        config = {
            "api_key": "dummy_key",
            "api_secret": "dummy_secret"
        }
        api = UpbitLiveAPI(config)
        
        # Act & Assert
        with pytest.raises(ReadOnlyError):
            api.cancel_order("order_123")
        
        print("[D98-3_TEST_PASS] UpbitLiveAPI.cancel_order blocked by decorator")


class TestBinanceLiveAPIReadOnlyGuard:
    """D98-3: BinanceLiveAPI Defense-in-depth Tests"""
    
    def test_binance_live_api_place_order_blocks_when_readonly_true(self):
        """
        [DEFENSE-IN-DEPTH] BinanceLiveAPI.place_order 데코레이터 차단
        
        Expected:
        - @enforce_readonly 데코레이터가 차단
        - ReadOnlyError 발생
        """
        from arbitrage.binance_live import BinanceLiveAPI
        from arbitrage.live_api import OrderRequest
        from arbitrage.types import OrderSide
        
        # Arrange
        set_readonly_mode(True)
        
        config = {
            "api_key": "dummy_key",
            "api_secret": "dummy_secret"
        }
        api = BinanceLiveAPI(config)
        
        order = OrderRequest(
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            quantity=0.01,
            price=50000.0,
            order_type="LIMIT"
        )
        
        # Act & Assert
        with pytest.raises(ReadOnlyError) as exc_info:
            api.place_order(order)
        
        assert "READ_ONLY" in str(exc_info.value).upper()
        print("[D98-3_TEST_PASS] BinanceLiveAPI.place_order blocked by decorator")
    
    def test_binance_live_api_cancel_order_blocks_when_readonly_true(self):
        """
        [DEFENSE-IN-DEPTH] BinanceLiveAPI.cancel_order 데코레이터 차단
        
        Expected:
        - @enforce_readonly 데코레이터가 차단
        - ReadOnlyError 발생
        """
        from arbitrage.binance_live import BinanceLiveAPI
        
        # Arrange
        set_readonly_mode(True)
        
        config = {
            "api_key": "dummy_key",
            "api_secret": "dummy_secret"
        }
        api = BinanceLiveAPI(config)
        
        # Act & Assert
        with pytest.raises(ReadOnlyError):
            api.cancel_order("order_456")
        
        print("[D98-3_TEST_PASS] BinanceLiveAPI.cancel_order blocked by decorator")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
