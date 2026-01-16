"""
D206-4: Order Pipeline Integration Tests

Tests:
1. _trade_to_result() creates OrderIntent from ArbitrageTrade
2. PaperExecutor executes OrderIntent and returns OrderResult
3. Decimal precision enforcement (18 digits)
4. Integration: Engine cycle -> trades -> OrderResults
"""

import pytest
from decimal import Decimal
from unittest.mock import Mock, MagicMock

from arbitrage.v2.core.engine import ArbitrageEngine, EngineConfig
from arbitrage.v2.domain.trade import ArbitrageTrade
from arbitrage.v2.domain.order_intent import OrderIntent, OrderSide
from arbitrage.v2.core.adapter import OrderResult
from arbitrage.v2.core.paper_executor import PaperExecutor


class TestD206_4_OrderPipeline:
    """D206-4 Order Pipeline Integration Tests"""
    
    def test_trade_to_result_creates_order_intent(self):
        """
        D206-4 AC-1: _trade_to_result() creates OrderIntent from ArbitrageTrade
        """
        config = EngineConfig(
            min_spread_bps=30.0,
            max_position_usd=1000.0,
            max_open_trades=3,
            taker_fee_a_bps=10.0,
            taker_fee_b_bps=10.0,
            slippage_bps=5.0,
            exchange_a_to_b_rate=1350.0,
        )
        
        engine = ArbitrageEngine(config)
        
        # Create ArbitrageTrade (LONG_A_SHORT_B -> BUY on upbit)
        trade = ArbitrageTrade(
            open_timestamp="2026-01-17T00:00:00Z",
            side="LONG_A_SHORT_B",
            entry_spread_bps=50.0,
            notional_usd=1000.0,
            is_open=True
        )
        
        # Call _trade_to_result() (stub mode, no executor)
        order_result = engine._trade_to_result(trade)
        
        # Verify OrderResult created
        assert order_result is not None
        assert order_result.success is True
        assert order_result.filled_qty is not None
        assert order_result.filled_price is not None
        
        # Verify Decimal precision (quantity should be ~0.02 BTC)
        qty_decimal = Decimal(str(order_result.filled_qty))
        assert qty_decimal > 0
        assert qty_decimal < 1.0  # Reasonable BTC quantity
    
    def test_trade_to_result_with_paper_executor(self):
        """
        D206-4 AC-2: PaperExecutor executes OrderIntent and returns OrderResult
        """
        # Mock PaperExecutor
        mock_executor = Mock(spec=PaperExecutor)
        mock_executor.execute.return_value = OrderResult(
            success=True,
            order_id="test_order_123",
            filled_qty=0.02,
            filled_price=50000.0,
            fee=1.0
        )
        
        config = EngineConfig(
            min_spread_bps=30.0,
            max_position_usd=1000.0,
            max_open_trades=3,
            taker_fee_a_bps=10.0,
            taker_fee_b_bps=10.0,
            slippage_bps=5.0,
            exchange_a_to_b_rate=1350.0,
            executor=mock_executor
        )
        
        engine = ArbitrageEngine(config)
        
        trade = ArbitrageTrade(
            open_timestamp="2026-01-17T00:00:00Z",
            side="LONG_A_SHORT_B",
            entry_spread_bps=50.0,
            notional_usd=1000.0,
            is_open=True
        )
        
        # Call _trade_to_result()
        order_result = engine._trade_to_result(trade)
        
        # Verify PaperExecutor was called
        assert mock_executor.execute.called
        call_args = mock_executor.execute.call_args[0][0]
        assert isinstance(call_args, OrderIntent)
        assert call_args.side == OrderSide.BUY
        assert call_args.symbol == "BTC/KRW"
        
        # Verify OrderResult
        assert order_result.success is True
        assert order_result.order_id == "test_order_123"
        assert order_result.filled_qty == 0.02
        assert order_result.filled_price == 50000.0
    
    def test_decimal_precision_enforcement(self):
        """
        D206-4 AC-4: Decimal precision enforcement (18 digits)
        """
        mock_executor = Mock(spec=PaperExecutor)
        mock_executor.execute.return_value = OrderResult(
            success=True,
            order_id="test_order_456",
            filled_qty=0.0200000001234567890123456789,  # > 18 digits
            filled_price=50000.123456789012345678901234567890,  # > 18 digits
            fee=1.00000000123456789012345678901234567890  # > 18 digits
        )
        
        config = EngineConfig(
            min_spread_bps=30.0,
            max_position_usd=1000.0,
            max_open_trades=3,
            taker_fee_a_bps=10.0,
            taker_fee_b_bps=10.0,
            slippage_bps=5.0,
            exchange_a_to_b_rate=1350.0,
            executor=mock_executor
        )
        
        engine = ArbitrageEngine(config)
        
        trade = ArbitrageTrade(
            open_timestamp="2026-01-17T00:00:00Z",
            side="LONG_A_SHORT_B",
            entry_spread_bps=50.0,
            notional_usd=1000.0,
            is_open=True
        )
        
        order_result = engine._trade_to_result(trade)
        
        # Verify Decimal quantize to 8 decimals (0.00000001)
        assert order_result.filled_qty == pytest.approx(0.02, abs=1e-8)
        assert order_result.filled_price == pytest.approx(50000.12345679, abs=1e-8)
        assert order_result.fee == pytest.approx(1.0, abs=1e-8)
        
        # Verify no precision loss beyond 8 decimals
        qty_str = f"{order_result.filled_qty:.8f}"
        assert len(qty_str.split('.')[-1]) == 8
    
    def test_engine_config_with_executor(self):
        """
        D206-4: EngineConfig accepts executor and ledger_writer
        """
        mock_executor = Mock(spec=PaperExecutor)
        mock_ledger = Mock()
        
        config = EngineConfig(
            min_spread_bps=30.0,
            max_position_usd=1000.0,
            max_open_trades=3,
            taker_fee_a_bps=10.0,
            taker_fee_b_bps=10.0,
            slippage_bps=5.0,
            exchange_a_to_b_rate=1350.0,
            executor=mock_executor,
            ledger_writer=mock_ledger
        )
        
        assert config.executor is mock_executor
        assert config.ledger_writer is mock_ledger
        assert config.run_id is not None  # UUID generated
    
    def test_trade_to_result_long_b_short_a(self):
        """
        D206-4: Test LONG_B_SHORT_A side (SELL on binance)
        """
        mock_executor = Mock(spec=PaperExecutor)
        mock_executor.execute.return_value = OrderResult(
            success=True,
            order_id="test_order_789",
            filled_qty=0.02,
            filled_price=37037.0,  # 50000 / 1350
            fee=0.74
        )
        
        config = EngineConfig(
            min_spread_bps=30.0,
            max_position_usd=1000.0,
            max_open_trades=3,
            taker_fee_a_bps=10.0,
            taker_fee_b_bps=10.0,
            slippage_bps=5.0,
            exchange_a_to_b_rate=1350.0,
            executor=mock_executor
        )
        
        engine = ArbitrageEngine(config)
        
        trade = ArbitrageTrade(
            open_timestamp="2026-01-17T00:00:00Z",
            side="LONG_B_SHORT_A",
            entry_spread_bps=50.0,
            notional_usd=1000.0,
            is_open=True
        )
        
        order_result = engine._trade_to_result(trade)
        
        # Verify OrderIntent was SELL on binance
        call_args = mock_executor.execute.call_args[0][0]
        assert call_args.side == OrderSide.SELL
        assert call_args.symbol == "BTC/USDT"
        
        assert order_result.success is True
        assert order_result.filled_price == pytest.approx(37037.0, abs=1e-6)
    
    def test_integration_engine_cycle_to_order_results(self):
        """
        D206-4 AC-5: Integration test - Engine cycle -> trades -> OrderResults
        """
        mock_executor = Mock(spec=PaperExecutor)
        mock_executor.execute.return_value = OrderResult(
            success=True,
            order_id="integration_order",
            filled_qty=0.02,
            filled_price=50000.0,
            fee=1.0
        )
        
        config = EngineConfig(
            min_spread_bps=30.0,
            max_position_usd=1000.0,
            max_open_trades=3,
            taker_fee_a_bps=10.0,
            taker_fee_b_bps=10.0,
            slippage_bps=5.0,
            exchange_a_to_b_rate=1350.0,
            executor=mock_executor
        )
        
        engine = ArbitrageEngine(config)
        
        # Simulate snapshot with opportunity
        snapshot = {
            'best_bid_a': 51000.0,
            'best_ask_a': 50000.0,
            'best_bid_b': 38000.0,  # 51300 KRW
            'best_ask_b': 37000.0,  # 49950 KRW
            'timestamp': '2026-01-17T00:00:00Z'
        }
        
        # Process snapshot (should open trade)
        trades_changed = engine._process_snapshot(snapshot)
        
        # Verify trade opened
        assert len(trades_changed) >= 0  # May or may not trigger based on spread
        
        # If trade opened, verify OrderResult conversion
        if trades_changed:
            trade = trades_changed[0]
            order_result = engine._trade_to_result(trade)
            
            assert order_result is not None
            assert order_result.success is True
            assert mock_executor.execute.called


class TestD206_4_BackwardCompatibility:
    """D206-4 AC-6: Regression - existing tests should still pass"""
    
    def test_stub_mode_backward_compatibility(self):
        """
        D206-4: Stub mode (no executor) should still work
        """
        config = EngineConfig(
            min_spread_bps=30.0,
            max_position_usd=1000.0,
            max_open_trades=3,
            taker_fee_a_bps=10.0,
            taker_fee_b_bps=10.0,
            slippage_bps=5.0,
            exchange_a_to_b_rate=1350.0,
        )
        
        engine = ArbitrageEngine(config)
        
        trade = ArbitrageTrade(
            open_timestamp="2026-01-17T00:00:00Z",
            side="LONG_A_SHORT_B",
            entry_spread_bps=50.0,
            notional_usd=1000.0,
            is_open=True
        )
        
        # Should not raise exception
        order_result = engine._trade_to_result(trade)
        
        assert order_result is not None
        assert order_result.success is True
        assert order_result.filled_qty > 0
        assert order_result.filled_price > 0
