"""
D201-1: BinanceAdapter MARKET Semantics Contract Tests

Tests for Binance Spot MARKET order translation.
"""

import pytest

from arbitrage.v2.core import OrderIntent, OrderSide, OrderType
from arbitrage.v2.adapters import BinanceAdapter


class TestBinanceAdapterMarketSemantics:
    """Contract tests for BinanceAdapter MARKET semantics"""
    
    def setup_method(self):
        """Setup test fixtures"""
        self.adapter = BinanceAdapter(read_only=True)
    
    def test_market_buy_translate(self):
        """
        TC-1: MARKET BUY translation
        
        OrderIntent (BUY MARKET quote_amount=100) 
        → Binance payload (quoteOrderQty="100.00000000")
        """
        intent = OrderIntent(
            exchange="binance",
            symbol="BTC/USDT",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quote_amount=100.00
        )
        
        payload = self.adapter.translate_intent(intent)
        
        assert payload["symbol"] == "BTCUSDT"
        assert payload["side"] == "BUY"
        assert payload["type"] == "MARKET"
        assert "quoteOrderQty" in payload
        assert float(payload["quoteOrderQty"]) == 100.00
        assert "quantity" not in payload  # quoteOrderQty 사용 시 금지
    
    def test_market_sell_translate(self):
        """
        TC-2: MARKET SELL translation
        
        OrderIntent (SELL MARKET base_qty=0.001) 
        → Binance payload (quantity="0.00100000")
        """
        intent = OrderIntent(
            exchange="binance",
            symbol="BTC/USDT",
            side=OrderSide.SELL,
            order_type=OrderType.MARKET,
            base_qty=0.001
        )
        
        payload = self.adapter.translate_intent(intent)
        
        assert payload["symbol"] == "BTCUSDT"
        assert payload["side"] == "SELL"
        assert payload["type"] == "MARKET"
        assert "quantity" in payload
        assert float(payload["quantity"]) == 0.001
        assert "quoteOrderQty" not in payload
    
    def test_limit_buy_translate(self):
        """
        TC-3: LIMIT BUY translation
        
        OrderIntent (BUY LIMIT quote_amount=100 @ 50000) 
        → Binance payload (quantity computed, price set)
        """
        intent = OrderIntent(
            exchange="binance",
            symbol="BTC/USDT",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quote_amount=100.00,
            limit_price=50000.00
        )
        
        payload = self.adapter.translate_intent(intent)
        
        assert payload["symbol"] == "BTCUSDT"
        assert payload["side"] == "BUY"
        assert payload["type"] == "LIMIT"
        assert "quantity" in payload
        assert float(payload["price"]) == 50000.00
        assert float(payload["quantity"]) == pytest.approx(0.002, rel=1e-8)
        assert "quoteOrderQty" not in payload
    
    def test_limit_sell_translate(self):
        """
        TC-4: LIMIT SELL translation
        
        OrderIntent (SELL LIMIT base_qty=0.001 @ 50000) 
        → Binance payload (quantity, price)
        """
        intent = OrderIntent(
            exchange="binance",
            symbol="BTC/USDT",
            side=OrderSide.SELL,
            order_type=OrderType.LIMIT,
            base_qty=0.001,
            limit_price=50000.00
        )
        
        payload = self.adapter.translate_intent(intent)
        
        assert payload["symbol"] == "BTCUSDT"
        assert payload["side"] == "SELL"
        assert payload["type"] == "LIMIT"
        assert "quantity" in payload
        assert float(payload["quantity"]) == 0.001
        assert float(payload["price"]) == 50000.00
        assert "quoteOrderQty" not in payload
    
    def test_symbol_transformation(self):
        """
        TC-5: Symbol format transformation
        
        V2 format (BTC/USDT) → Binance format (BTCUSDT)
        """
        intent = OrderIntent(
            exchange="binance",
            symbol="ETH/USDT",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quote_amount=50.00
        )
        
        payload = self.adapter.translate_intent(intent)
        
        assert payload["symbol"] == "ETHUSDT"
    
    def test_market_buy_missing_quote_amount(self):
        """
        TC-6: MARKET BUY without quote_amount should fail
        """
        intent = OrderIntent(
            exchange="binance",
            symbol="BTC/USDT",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quote_amount=None
        )
        
        with pytest.raises(ValueError, match="quote_amount"):
            self.adapter.translate_intent(intent)
    
    def test_market_sell_missing_base_qty(self):
        """
        TC-7: MARKET SELL without base_qty should fail
        """
        intent = OrderIntent(
            exchange="binance",
            symbol="BTC/USDT",
            side=OrderSide.SELL,
            order_type=OrderType.MARKET,
            base_qty=None
        )
        
        with pytest.raises(ValueError, match="base_qty"):
            self.adapter.translate_intent(intent)
    
    def test_limit_missing_price(self):
        """
        TC-8: LIMIT order without limit_price should fail
        """
        intent = OrderIntent(
            exchange="binance",
            symbol="BTC/USDT",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quote_amount=100.00,
            limit_price=None
        )
        
        with pytest.raises(ValueError, match="limit_price"):
            self.adapter.translate_intent(intent)
    
    def test_execute_flow_mock(self):
        """
        TC-9: Full execution flow (translate → submit → parse)
        
        Mock mode should return success=True
        """
        intent = OrderIntent(
            exchange="binance",
            symbol="BTC/USDT",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quote_amount=100.00
        )
        
        result = self.adapter.execute(intent)
        
        assert result.success is True
        assert result.order_id is not None
        assert result.raw_response is not None
    
    def test_antipattern_limit_as_market(self):
        """
        TC-10: Anti-pattern detection
        
        LIMIT order with extreme price should NOT be treated as MARKET
        """
        intent = OrderIntent(
            exchange="binance",
            symbol="BTC/USDT",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quote_amount=100.00,
            limit_price=99999999.00
        )
        
        payload = self.adapter.translate_intent(intent)
        
        # LIMIT으로 명시되어야 함 (MARKET이 아님)
        assert payload["type"] == "LIMIT"
        assert "price" in payload
        assert "timeInForce" in payload
