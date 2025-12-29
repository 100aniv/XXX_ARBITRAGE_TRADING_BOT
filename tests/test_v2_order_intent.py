"""
Test OrderIntent validation (D201-2)

V2 계약 검증:
- MARKET BUY: quote_amount 필수
- MARKET SELL: base_qty 필수
- LIMIT 주문: limit_price 필수
"""
import pytest
from arbitrage.v2.core.order_intent import OrderIntent, OrderSide, OrderType


class TestOrderIntentValidation:
    """OrderIntent 유효성 검증 (V2 계약)"""

    def test_market_buy_requires_quote_amount(self):
        """TC-1: MARKET BUY는 quote_amount 필수"""
        intent = OrderIntent(
            exchange="binance",
            symbol="BTC/USDT",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quote_amount=None
        )
        
        with pytest.raises(ValueError, match="MARKET BUY requires positive quote_amount"):
            intent.validate()

    def test_market_buy_requires_positive_quote_amount(self):
        """TC-2: MARKET BUY quote_amount는 양수여야 함"""
        intent = OrderIntent(
            exchange="binance",
            symbol="BTC/USDT",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quote_amount=0
        )
        
        with pytest.raises(ValueError, match="MARKET BUY requires positive quote_amount"):
            intent.validate()

    def test_market_buy_valid(self):
        """TC-3: MARKET BUY 정상 케이스"""
        intent = OrderIntent(
            exchange="binance",
            symbol="BTC/USDT",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quote_amount=100.0
        )
        
        intent.validate()

    def test_market_sell_requires_base_qty(self):
        """TC-4: MARKET SELL은 base_qty 필수"""
        intent = OrderIntent(
            exchange="binance",
            symbol="BTC/USDT",
            side=OrderSide.SELL,
            order_type=OrderType.MARKET,
            base_qty=None
        )
        
        with pytest.raises(ValueError, match="MARKET SELL requires positive base_qty"):
            intent.validate()

    def test_market_sell_requires_positive_base_qty(self):
        """TC-5: MARKET SELL base_qty는 양수여야 함"""
        intent = OrderIntent(
            exchange="binance",
            symbol="BTC/USDT",
            side=OrderSide.SELL,
            order_type=OrderType.MARKET,
            base_qty=0
        )
        
        with pytest.raises(ValueError, match="MARKET SELL requires positive base_qty"):
            intent.validate()

    def test_market_sell_valid(self):
        """TC-6: MARKET SELL 정상 케이스"""
        intent = OrderIntent(
            exchange="binance",
            symbol="BTC/USDT",
            side=OrderSide.SELL,
            order_type=OrderType.MARKET,
            base_qty=0.001
        )
        
        intent.validate()

    def test_limit_buy_requires_limit_price(self):
        """TC-7: LIMIT BUY는 limit_price 필수"""
        intent = OrderIntent(
            exchange="binance",
            symbol="BTC/USDT",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quote_amount=100.0,
            limit_price=None
        )
        
        with pytest.raises(ValueError, match="LIMIT order requires positive limit_price"):
            intent.validate()

    def test_limit_buy_requires_quote_amount(self):
        """TC-8: LIMIT BUY는 quote_amount 필수"""
        intent = OrderIntent(
            exchange="binance",
            symbol="BTC/USDT",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quote_amount=None,
            limit_price=50000.0
        )
        
        with pytest.raises(ValueError, match="LIMIT BUY requires positive quote_amount"):
            intent.validate()

    def test_limit_buy_valid(self):
        """TC-9: LIMIT BUY 정상 케이스"""
        intent = OrderIntent(
            exchange="binance",
            symbol="BTC/USDT",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quote_amount=100.0,
            limit_price=50000.0
        )
        
        intent.validate()

    def test_limit_sell_requires_limit_price(self):
        """TC-10: LIMIT SELL은 limit_price 필수"""
        intent = OrderIntent(
            exchange="binance",
            symbol="BTC/USDT",
            side=OrderSide.SELL,
            order_type=OrderType.LIMIT,
            base_qty=0.001,
            limit_price=None
        )
        
        with pytest.raises(ValueError, match="LIMIT order requires positive limit_price"):
            intent.validate()

    def test_limit_sell_requires_base_qty(self):
        """TC-11: LIMIT SELL은 base_qty 필수"""
        intent = OrderIntent(
            exchange="binance",
            symbol="BTC/USDT",
            side=OrderSide.SELL,
            order_type=OrderType.LIMIT,
            base_qty=None,
            limit_price=50000.0
        )
        
        with pytest.raises(ValueError, match="LIMIT SELL requires positive base_qty"):
            intent.validate()

    def test_limit_sell_valid(self):
        """TC-12: LIMIT SELL 정상 케이스"""
        intent = OrderIntent(
            exchange="binance",
            symbol="BTC/USDT",
            side=OrderSide.SELL,
            order_type=OrderType.LIMIT,
            base_qty=0.001,
            limit_price=50000.0
        )
        
        intent.validate()

    def test_repr_market_buy(self):
        """TC-13: __repr__ MARKET BUY 포맷"""
        intent = OrderIntent(
            exchange="binance",
            symbol="BTC/USDT",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quote_amount=100.0
        )
        
        repr_str = repr(intent)
        assert "BTC/USDT" in repr_str
        assert "BUY" in repr_str
        assert "MARKET" in repr_str
        assert "quote_amount=100.0" in repr_str

    def test_repr_market_sell(self):
        """TC-14: __repr__ MARKET SELL 포맷"""
        intent = OrderIntent(
            exchange="binance",
            symbol="BTC/USDT",
            side=OrderSide.SELL,
            order_type=OrderType.MARKET,
            base_qty=0.001
        )
        
        repr_str = repr(intent)
        assert "BTC/USDT" in repr_str
        assert "SELL" in repr_str
        assert "MARKET" in repr_str
        assert "base_qty=0.001" in repr_str
