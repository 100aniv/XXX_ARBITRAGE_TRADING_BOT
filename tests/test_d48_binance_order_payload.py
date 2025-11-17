"""
D48: Binance 주문 페이로드 테스트

create_order / cancel_order의 REST API 페이로드 검증
"""

import pytest
from unittest.mock import Mock, patch
import requests

from arbitrage.exchanges.binance_futures import BinanceFuturesExchange
from arbitrage.exchanges.base import OrderSide, OrderType, TimeInForce
from arbitrage.exchanges.exceptions import AuthenticationError, NetworkError


class TestD48BinanceOrderPayload:
    """D48 Binance 주문 페이로드 테스트"""

    def test_binance_create_order_live_disabled(self):
        """live_enabled=False일 때 주문 생성 차단"""
        config = {
            "api_key": "test_key",
            "api_secret": "test_secret",
            "base_url": "https://fapi.binance.com",
            "live_enabled": False,
        }
        
        exchange = BinanceFuturesExchange(config)
        
        with pytest.raises(RuntimeError) as exc_info:
            exchange.create_order(
                symbol="BTCUSDT",
                side=OrderSide.BUY,
                qty=0.01,
                price=40000,
            )
        
        assert "Live trading is disabled" in str(exc_info.value)

    def test_binance_create_order_no_api_key(self):
        """API 키 없을 때 에러"""
        config = {
            "api_key": "",
            "api_secret": "",
            "base_url": "https://fapi.binance.com",
            "live_enabled": True,
        }
        
        exchange = BinanceFuturesExchange(config)
        
        with pytest.raises(AuthenticationError):
            exchange.create_order(
                symbol="BTCUSDT",
                side=OrderSide.BUY,
                qty=0.01,
                price=40000,
            )

    @patch('arbitrage.exchanges.binance_futures.HTTPClient.post')
    def test_binance_create_order_success(self, mock_post):
        """주문 생성 성공"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "orderId": 12345,
            "status": "NEW",
            "executedQty": 0.0,
        }
        mock_post.return_value = mock_response
        
        config = {
            "api_key": "test_key",
            "api_secret": "test_secret",
            "base_url": "https://fapi.binance.com",
            "live_enabled": True,
        }
        
        exchange = BinanceFuturesExchange(config)
        result = exchange.create_order(
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            qty=0.01,
            price=40000,
            order_type=OrderType.LIMIT,
        )
        
        assert result.order_id == "12345"
        assert result.symbol == "BTCUSDT"
        assert result.qty == 0.01
        assert result.price == 40000
        
        # 호출 검증
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        # call_args[0]은 positional args, call_args[1]은 kwargs
        assert call_args[0][0] == "https://fapi.binance.com/fapi/v1/order"
        assert "X-MBX-APIKEY" in call_args[1]["headers"]

    @patch('arbitrage.exchanges.binance_futures.HTTPClient.post')
    def test_binance_create_order_payload_structure(self, mock_post):
        """주문 페이로드 구조 검증"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "orderId": 12345,
            "status": "NEW",
            "executedQty": 0.0,
        }
        mock_post.return_value = mock_response
        
        config = {
            "api_key": "test_key",
            "api_secret": "test_secret",
            "base_url": "https://fapi.binance.com",
            "live_enabled": True,
        }
        
        exchange = BinanceFuturesExchange(config)
        exchange.create_order(
            symbol="BTCUSDT",
            side=OrderSide.SELL,
            qty=0.5,
            price=45000,
        )
        
        # 페이로드 검증
        call_kwargs = mock_post.call_args[1]
        params = call_kwargs["params"]
        
        assert params["symbol"] == "BTCUSDT"
        assert params["side"] == "SELL"
        assert params["quantity"] == "0.5"
        assert params["price"] == "45000"
        assert params["type"] == "LIMIT"
        assert params["timeInForce"] == "GTC"
        assert "timestamp" in params
        assert "signature" in params

    @patch('arbitrage.exchanges.binance_futures.HTTPClient.post')
    def test_binance_create_order_signature_header(self, mock_post):
        """서명 헤더 검증"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "orderId": 12345,
            "status": "NEW",
            "executedQty": 0.0,
        }
        mock_post.return_value = mock_response
        
        config = {
            "api_key": "test_key",
            "api_secret": "test_secret",
            "base_url": "https://fapi.binance.com",
            "live_enabled": True,
        }
        
        exchange = BinanceFuturesExchange(config)
        exchange.create_order(
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            qty=0.01,
            price=40000,
        )
        
        # 헤더 검증
        call_kwargs = mock_post.call_args[1]
        headers = call_kwargs["headers"]
        
        assert "X-MBX-APIKEY" in headers
        assert headers["X-MBX-APIKEY"] == "test_key"

    @patch('arbitrage.exchanges.binance_futures.HTTPClient.delete')
    def test_binance_cancel_order_success(self, mock_delete):
        """주문 취소 성공"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_delete.return_value = mock_response
        
        config = {
            "api_key": "test_key",
            "api_secret": "test_secret",
            "base_url": "https://fapi.binance.com",
            "live_enabled": True,
        }
        
        exchange = BinanceFuturesExchange(config)
        result = exchange.cancel_order("12345", symbol="BTCUSDT")
        
        assert result is True
        mock_delete.assert_called_once()

    def test_binance_cancel_order_live_disabled(self):
        """live_enabled=False일 때 주문 취소 차단"""
        config = {
            "api_key": "test_key",
            "api_secret": "test_secret",
            "base_url": "https://fapi.binance.com",
            "live_enabled": False,
        }
        
        exchange = BinanceFuturesExchange(config)
        
        with pytest.raises(RuntimeError) as exc_info:
            exchange.cancel_order("12345")
        
        assert "Live trading is disabled" in str(exc_info.value)

    @patch('arbitrage.exchanges.binance_futures.HTTPClient.post')
    def test_binance_create_order_network_error(self, mock_post):
        """네트워크 에러 처리"""
        mock_post.side_effect = requests.RequestException("Connection failed")
        
        config = {
            "api_key": "test_key",
            "api_secret": "test_secret",
            "base_url": "https://fapi.binance.com",
            "live_enabled": True,
        }
        
        exchange = BinanceFuturesExchange(config)
        
        with pytest.raises(NetworkError):
            exchange.create_order(
                symbol="BTCUSDT",
                side=OrderSide.BUY,
                qty=0.01,
                price=40000,
            )

    @patch('arbitrage.exchanges.binance_futures.HTTPClient.post')
    def test_binance_create_order_parse_error(self, mock_post):
        """응답 파싱 에러 처리"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.side_effect = ValueError("Invalid JSON")
        mock_post.return_value = mock_response
        
        config = {
            "api_key": "test_key",
            "api_secret": "test_secret",
            "base_url": "https://fapi.binance.com",
            "live_enabled": True,
        }
        
        exchange = BinanceFuturesExchange(config)
        
        with pytest.raises(NetworkError):
            exchange.create_order(
                symbol="BTCUSDT",
                side=OrderSide.BUY,
                qty=0.01,
                price=40000,
            )

    @patch('arbitrage.exchanges.binance_futures.HTTPClient.post')
    def test_binance_create_order_market_type(self, mock_post):
        """시장가 주문 (MARKET 타입)"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "orderId": 12345,
            "status": "NEW",
            "executedQty": 0.0,
        }
        mock_post.return_value = mock_response
        
        config = {
            "api_key": "test_key",
            "api_secret": "test_secret",
            "base_url": "https://fapi.binance.com",
            "live_enabled": True,
        }
        
        exchange = BinanceFuturesExchange(config)
        exchange.create_order(
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            qty=0.01,
            order_type=OrderType.MARKET,
        )
        
        # 페이로드 검증
        call_kwargs = mock_post.call_args[1]
        params = call_kwargs["params"]
        
        assert params["type"] == "MARKET"
        assert "price" not in params  # 시장가는 가격 없음

    @patch('arbitrage.exchanges.binance_futures.HTTPClient.delete')
    def test_binance_cancel_order_payload(self, mock_delete):
        """취소 주문 페이로드 검증"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_delete.return_value = mock_response
        
        config = {
            "api_key": "test_key",
            "api_secret": "test_secret",
            "base_url": "https://fapi.binance.com",
            "live_enabled": True,
        }
        
        exchange = BinanceFuturesExchange(config)
        exchange.cancel_order("12345", symbol="BTCUSDT")
        
        # 페이로드 검증
        call_kwargs = mock_delete.call_args[1]
        params = call_kwargs["params"]
        
        assert params["orderId"] == "12345"
        assert params["symbol"] == "BTCUSDT"
        assert "timestamp" in params
        assert "signature" in params
