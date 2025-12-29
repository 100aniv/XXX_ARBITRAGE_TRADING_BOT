"""
Test Adapter Contract (D201-2)

V2 계약 검증:
- Mock/Upbit/Binance Adapter가 동일한 계약을 만족하는지 검증
- MARKET BUY: quote_amount 기반
- MARKET SELL: base_qty 기반
"""
import pytest
from arbitrage.v2.core.order_intent import OrderIntent, OrderSide, OrderType
from arbitrage.v2.adapters.binance_adapter import BinanceAdapter
from arbitrage.v2.adapters.upbit_adapter import UpbitAdapter
from arbitrage.v2.adapters.mock_adapter import MockAdapter


class TestBinanceAdapterContract:
    """BinanceAdapter 계약 검증"""

    def test_market_buy_uses_quote_order_qty(self):
        """TC-1: MARKET BUY는 quoteOrderQty 사용 (USDT amount)"""
        adapter = BinanceAdapter(read_only=True)
        
        intent = OrderIntent(
            exchange="binance",
            symbol="BTC/USDT",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quote_amount=100.0
        )
        
        payload = adapter.translate_intent(intent)
        
        assert "quoteOrderQty" in payload
        assert payload["quoteOrderQty"] == "100.00000000"
        assert "quantity" not in payload

    def test_market_sell_uses_quantity(self):
        """TC-2: MARKET SELL은 quantity 사용 (BTC amount)"""
        adapter = BinanceAdapter(read_only=True)
        
        intent = OrderIntent(
            exchange="binance",
            symbol="BTC/USDT",
            side=OrderSide.SELL,
            order_type=OrderType.MARKET,
            base_qty=0.001
        )
        
        payload = adapter.translate_intent(intent)
        
        assert "quantity" in payload
        assert payload["quantity"] == "0.00100000"
        assert "quoteOrderQty" not in payload

    def test_market_buy_missing_quote_amount_raises_error(self):
        """TC-3: MARKET BUY에서 quote_amount 누락 시 ValueError"""
        adapter = BinanceAdapter(read_only=True)
        
        intent = OrderIntent(
            exchange="binance",
            symbol="BTC/USDT",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quote_amount=None
        )
        
        with pytest.raises(ValueError):
            adapter.translate_intent(intent)

    def test_market_sell_missing_base_qty_raises_error(self):
        """TC-4: MARKET SELL에서 base_qty 누락 시 ValueError"""
        adapter = BinanceAdapter(read_only=True)
        
        intent = OrderIntent(
            exchange="binance",
            symbol="BTC/USDT",
            side=OrderSide.SELL,
            order_type=OrderType.MARKET,
            base_qty=None
        )
        
        with pytest.raises(ValueError):
            adapter.translate_intent(intent)

    def test_symbol_transformation(self):
        """TC-5: Symbol 변환 (BTC/USDT → BTCUSDT)"""
        adapter = BinanceAdapter(read_only=True)
        
        intent = OrderIntent(
            exchange="binance",
            symbol="BTC/USDT",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quote_amount=100.0
        )
        
        payload = adapter.translate_intent(intent)
        
        assert payload["symbol"] == "BTCUSDT"


class TestUpbitAdapterContract:
    """UpbitAdapter 계약 검증"""

    def test_market_buy_uses_price_krw_amount(self):
        """TC-6: MARKET BUY는 price 사용 (KRW amount = quote)"""
        adapter = UpbitAdapter(read_only=True)
        
        intent = OrderIntent(
            exchange="upbit",
            symbol="BTC/KRW",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quote_amount=100000.0
        )
        
        payload = adapter.translate_intent(intent)
        
        assert "price" in payload
        assert payload["price"] == "100000"
        assert "volume" not in payload

    def test_market_sell_uses_volume_coin_qty(self):
        """TC-7: MARKET SELL은 volume 사용 (coin qty = base)"""
        adapter = UpbitAdapter(read_only=True)
        
        intent = OrderIntent(
            exchange="upbit",
            symbol="BTC/KRW",
            side=OrderSide.SELL,
            order_type=OrderType.MARKET,
            base_qty=0.001
        )
        
        payload = adapter.translate_intent(intent)
        
        assert "volume" in payload
        assert payload["volume"] == "0.001"
        assert "price" not in payload

    def test_market_buy_missing_quote_amount_raises_error(self):
        """TC-8: MARKET BUY에서 quote_amount 누락 시 ValueError"""
        adapter = UpbitAdapter(read_only=True)
        
        intent = OrderIntent(
            exchange="upbit",
            symbol="BTC/KRW",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quote_amount=None
        )
        
        with pytest.raises(ValueError):
            adapter.translate_intent(intent)

    def test_market_sell_missing_base_qty_raises_error(self):
        """TC-9: MARKET SELL에서 base_qty 누락 시 ValueError"""
        adapter = UpbitAdapter(read_only=True)
        
        intent = OrderIntent(
            exchange="upbit",
            symbol="BTC/KRW",
            side=OrderSide.SELL,
            order_type=OrderType.MARKET,
            base_qty=None
        )
        
        with pytest.raises(ValueError):
            adapter.translate_intent(intent)

    def test_symbol_transformation(self):
        """TC-10: Symbol 변환 (BTC/KRW → KRW-BTC)"""
        adapter = UpbitAdapter(read_only=True)
        
        intent = OrderIntent(
            exchange="upbit",
            symbol="BTC/KRW",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quote_amount=100000.0
        )
        
        payload = adapter.translate_intent(intent)
        
        assert payload["market"] == "KRW-BTC"


class TestMockAdapterContract:
    """MockAdapter 계약 검증"""

    def test_market_buy_accepts_quote_amount(self):
        """TC-11: MockAdapter MARKET BUY는 quote_amount 받음"""
        adapter = MockAdapter()
        
        intent = OrderIntent(
            exchange="mock",
            symbol="BTC/USDT",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quote_amount=100.0
        )
        
        payload = adapter.translate_intent(intent)
        
        assert payload["side"] == "BUY"
        assert payload["order_type"] == "MARKET"

    def test_market_sell_accepts_base_qty(self):
        """TC-12: MockAdapter MARKET SELL은 base_qty 받음"""
        adapter = MockAdapter()
        
        intent = OrderIntent(
            exchange="mock",
            symbol="BTC/USDT",
            side=OrderSide.SELL,
            order_type=OrderType.MARKET,
            base_qty=0.001
        )
        
        payload = adapter.translate_intent(intent)
        
        assert payload["side"] == "SELL"
        assert payload["order_type"] == "MARKET"

    def test_contract_violation_raises_error(self):
        """TC-13: MockAdapter 계약 위반 시 ValueError"""
        adapter = MockAdapter()
        
        intent = OrderIntent(
            exchange="mock",
            symbol="BTC/USDT",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quote_amount=None
        )
        
        with pytest.raises(ValueError):
            adapter.translate_intent(intent)


class TestAdapterContractConsistency:
    """Adapter 간 계약 일관성 검증"""

    def test_all_adapters_reject_invalid_market_buy(self):
        """TC-14: 모든 Adapter가 invalid MARKET BUY를 거부"""
        adapters = [
            BinanceAdapter(read_only=True),
            UpbitAdapter(read_only=True),
            MockAdapter()
        ]
        
        intent = OrderIntent(
            exchange="test",
            symbol="BTC/USDT",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quote_amount=None
        )
        
        for adapter in adapters:
            with pytest.raises(ValueError):
                adapter.translate_intent(intent)

    def test_all_adapters_reject_invalid_market_sell(self):
        """TC-15: 모든 Adapter가 invalid MARKET SELL을 거부"""
        adapters = [
            BinanceAdapter(read_only=True),
            UpbitAdapter(read_only=True),
            MockAdapter()
        ]
        
        intent = OrderIntent(
            exchange="test",
            symbol="BTC/USDT",
            side=OrderSide.SELL,
            order_type=OrderType.MARKET,
            base_qty=None
        )
        
        for adapter in adapters:
            with pytest.raises(ValueError):
                adapter.translate_intent(intent)

    def test_all_adapters_accept_valid_market_buy(self):
        """TC-16: 모든 Adapter가 valid MARKET BUY를 수락"""
        adapters = [
            (BinanceAdapter(read_only=True), "BTC/USDT", 100.0),
            (UpbitAdapter(read_only=True), "BTC/KRW", 100000.0),
            (MockAdapter(), "BTC/USDT", 100.0)
        ]
        
        for adapter, symbol, quote_amount in adapters:
            intent = OrderIntent(
                exchange="test",
                symbol=symbol,
                side=OrderSide.BUY,
                order_type=OrderType.MARKET,
                quote_amount=quote_amount
            )
            
            payload = adapter.translate_intent(intent)
            assert payload is not None

    def test_all_adapters_accept_valid_market_sell(self):
        """TC-17: 모든 Adapter가 valid MARKET SELL을 수락"""
        adapters = [
            (BinanceAdapter(read_only=True), "BTC/USDT"),
            (UpbitAdapter(read_only=True), "BTC/KRW"),
            (MockAdapter(), "BTC/USDT")
        ]
        
        for adapter, symbol in adapters:
            intent = OrderIntent(
                exchange="test",
                symbol=symbol,
                side=OrderSide.SELL,
                order_type=OrderType.MARKET,
                base_qty=0.001
            )
            
            payload = adapter.translate_intent(intent)
            assert payload is not None
