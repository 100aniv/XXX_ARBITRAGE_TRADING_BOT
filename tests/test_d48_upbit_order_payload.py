"""
D48: Upbit 주문 페이로드 테스트

create_order / cancel_order의 REST API 페이로드 검증
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import requests

from arbitrage.exchanges.upbit_spot import UpbitSpotExchange
from arbitrage.exchanges.base import OrderSide, OrderType, TimeInForce
from arbitrage.exchanges.exceptions import AuthenticationError, NetworkError


class TestD48UpbitOrderPayload:
    """D48 Upbit 주문 페이로드 테스트"""

    def test_upbit_create_order_live_disabled(self):
        """live_enabled=False일 때 주문 생성 차단"""
        config = {
            "api_key": "test_key",
            "api_secret": "test_secret",
            "base_url": "https://api.upbit.com",
            "live_enabled": False,
        }
        
        exchange = UpbitSpotExchange(config)
        
        with pytest.raises(RuntimeError) as exc_info:
            exchange.create_order(
                symbol="KRW-BTC",
                side=OrderSide.BUY,
                qty=0.01,
                price=50000000,
            )
        
        assert "Live trading is disabled" in str(exc_info.value)

    def test_upbit_create_order_no_api_key(self):
        """API 키 없을 때 에러"""
        config = {
            "api_key": "",
            "api_secret": "",
            "base_url": "https://api.upbit.com",
            "live_enabled": True,
        }
        
        exchange = UpbitSpotExchange(config)
        
        with pytest.raises(AuthenticationError):
            exchange.create_order(
                symbol="KRW-BTC",
                side=OrderSide.BUY,
                qty=0.01,
                price=50000000,
            )

    @patch('arbitrage.exchanges.upbit_spot.HTTPClient.post')
    def test_upbit_create_order_success(self, mock_post):
        """주문 생성 성공"""
        mock_response = Mock()
        mock_response.status_code = 201
        mock_response.json.return_value = {
            "uuid": "upbit_order_123",
            "state": "wait",
            "executed_volume": 0.0,
        }
        mock_post.return_value = mock_response
        
        config = {
            "api_key": "test_key",
            "api_secret": "test_secret",
            "base_url": "https://api.upbit.com",
            "live_enabled": True,
        }
        
        exchange = UpbitSpotExchange(config)
        result = exchange.create_order(
            symbol="KRW-BTC",
            side=OrderSide.BUY,
            qty=0.01,
            price=50000000,
            order_type=OrderType.LIMIT,
        )
        
        assert result.order_id == "upbit_order_123"
        assert result.symbol == "KRW-BTC"
        assert result.qty == 0.01
        assert result.price == 50000000
        
        # 호출 검증
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        # call_args[0]은 positional args, call_args[1]은 kwargs
        assert call_args[0][0] == "https://api.upbit.com/v1/orders"
        assert "Authorization" in call_args[1]["headers"]

    @patch('arbitrage.exchanges.upbit_spot.HTTPClient.post')
    def test_upbit_create_order_payload_structure(self, mock_post):
        """주문 페이로드 구조 검증"""
        mock_response = Mock()
        mock_response.status_code = 201
        mock_response.json.return_value = {
            "uuid": "order_123",
            "state": "wait",
            "executed_volume": 0.0,
        }
        mock_post.return_value = mock_response
        
        config = {
            "api_key": "test_key",
            "api_secret": "test_secret",
            "base_url": "https://api.upbit.com",
            "live_enabled": True,
        }
        
        exchange = UpbitSpotExchange(config)
        exchange.create_order(
            symbol="KRW-BTC",
            side=OrderSide.SELL,
            qty=0.5,
            price=60000000,
        )
        
        # 호출 검증
        call_kwargs = mock_post.call_args[1]
        params = call_kwargs["params"]
        
        assert params["market"] == "KRW-BTC"
        assert params["side"] == "ask"  # SELL -> ask
        assert params["volume"] == "0.5"
        assert params["price"] == "60000000"
        assert params["ord_type"] == "limit"

    @patch('arbitrage.exchanges.upbit_spot.HTTPClient.post')
    def test_upbit_create_order_signature_header(self, mock_post):
        """서명 헤더 검증 (D106-3: JWT 인증)"""
        mock_response = Mock()
        mock_response.status_code = 201
        mock_response.json.return_value = {
            "uuid": "order_123",
            "state": "wait",
            "executed_volume": 0.0,
        }
        mock_post.return_value = mock_response
        
        config = {
            "api_key": "test_key",
            "api_secret": "test_secret",
            "base_url": "https://api.upbit.com",
            "live_enabled": True,
        }
        
        exchange = UpbitSpotExchange(config)
        exchange.create_order(
            symbol="KRW-BTC",
            side=OrderSide.BUY,
            qty=0.01,
            price=50000000,
        )
        
        # 헤더 검증 (D106-3: JWT 표준 인증)
        call_kwargs = mock_post.call_args[1]
        headers = call_kwargs["headers"]
        
        # JWT Authorization 헤더만 존재
        assert "Authorization" in headers
        assert headers["Authorization"].startswith("Bearer ")
        # JWT 토큰 형식 검증 (3개 파트: header.payload.signature)
        token = headers["Authorization"].split("Bearer ")[1]
        assert len(token.split(".")) == 3

    @patch('arbitrage.exchanges.upbit_spot.HTTPClient.delete')
    def test_upbit_cancel_order_success(self, mock_delete):
        """주문 취소 성공"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_delete.return_value = mock_response
        
        config = {
            "api_key": "test_key",
            "api_secret": "test_secret",
            "base_url": "https://api.upbit.com",
            "live_enabled": True,
        }
        
        exchange = UpbitSpotExchange(config)
        result = exchange.cancel_order("upbit_order_123")
        
        assert result is True
        mock_delete.assert_called_once()

    def test_upbit_cancel_order_live_disabled(self):
        """live_enabled=False일 때 주문 취소 차단"""
        config = {
            "api_key": "test_key",
            "api_secret": "test_secret",
            "base_url": "https://api.upbit.com",
            "live_enabled": False,
        }
        
        exchange = UpbitSpotExchange(config)
        
        with pytest.raises(RuntimeError) as exc_info:
            exchange.cancel_order("upbit_order_123")
        
        assert "Live trading is disabled" in str(exc_info.value)

    @patch('arbitrage.exchanges.upbit_spot.HTTPClient.post')
    def test_upbit_create_order_network_error(self, mock_post):
        """네트워크 에러 처리"""
        mock_post.side_effect = requests.RequestException("Connection failed")
        
        config = {
            "api_key": "test_key",
            "api_secret": "test_secret",
            "base_url": "https://api.upbit.com",
            "live_enabled": True,
        }
        
        exchange = UpbitSpotExchange(config)
        
        with pytest.raises(NetworkError):
            exchange.create_order(
                symbol="KRW-BTC",
                side=OrderSide.BUY,
                qty=0.01,
                price=50000000,
            )

    @patch('arbitrage.exchanges.upbit_spot.HTTPClient.post')
    def test_upbit_create_order_parse_error(self, mock_post):
        """응답 파싱 에러 처리"""
        mock_response = Mock()
        mock_response.status_code = 201
        mock_response.json.side_effect = ValueError("Invalid JSON")
        mock_post.return_value = mock_response
        
        config = {
            "api_key": "test_key",
            "api_secret": "test_secret",
            "base_url": "https://api.upbit.com",
            "live_enabled": True,
        }
        
        exchange = UpbitSpotExchange(config)
        
        with pytest.raises(NetworkError):
            exchange.create_order(
                symbol="KRW-BTC",
                side=OrderSide.BUY,
                qty=0.01,
                price=50000000,
            )

    @patch('arbitrage.exchanges.upbit_spot.HTTPClient.post')
    def test_upbit_create_order_market_type(self, mock_post):
        """시장가 주문 (MARKET 타입)"""
        mock_response = Mock()
        mock_response.status_code = 201
        mock_response.json.return_value = {
            "uuid": "order_123",
            "state": "wait",
            "executed_volume": 0.0,
        }
        mock_post.return_value = mock_response
        
        config = {
            "api_key": "test_key",
            "api_secret": "test_secret",
            "base_url": "https://api.upbit.com",
            "live_enabled": True,
        }
        
        exchange = UpbitSpotExchange(config)
        exchange.create_order(
            symbol="KRW-BTC",
            side=OrderSide.BUY,
            qty=0.01,
            order_type=OrderType.MARKET,
        )
        
        # 페이로드 검증
        call_kwargs = mock_post.call_args[1]
        params = call_kwargs["params"]
        
        assert params["ord_type"] == "market"
        assert "price" not in params  # 시장가는 가격 없음
