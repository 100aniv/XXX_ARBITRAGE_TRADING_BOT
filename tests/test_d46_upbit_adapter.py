"""
D46: Upbit Read-Only 어댑터 테스트

실제 API 호출 (mock 사용)을 통한 Upbit 어댑터 검증
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import requests
from arbitrage.exchanges.upbit_spot import UpbitSpotExchange
from arbitrage.exchanges.exceptions import NetworkError, AuthenticationError


class TestD46UpbitAdapter:
    """D46 Upbit Read-Only 어댑터 테스트"""

    def test_upbit_initialization(self):
        """Upbit 어댑터 초기화"""
        config = {
            "api_key": "test_key",
            "api_secret": "test_secret",
            "base_url": "https://api.upbit.com",
            "timeout": 10,
            "live_enabled": False,
        }
        
        exchange = UpbitSpotExchange(config)
        
        assert exchange.name == "upbit"
        assert exchange.api_key == "test_key"
        assert exchange.api_secret == "test_secret"
        assert exchange.live_enabled is False

    @patch("requests.get")
    def test_get_orderbook_success(self, mock_get):
        """호가 조회 성공"""
        config = {
            "api_key": "test_key",
            "api_secret": "test_secret",
            "base_url": "https://api.upbit.com",
            "timeout": 10,
        }
        
        exchange = UpbitSpotExchange(config)
        
        # Mock 응답
        mock_response = Mock()
        mock_response.json.return_value = {
            "market": "BTC-KRW",
            "timestamp": 1234567890000,
            "orderbook_units": [
                {
                    "ask_price": 100500.0,
                    "ask_size": 1.0,
                    "bid_price": 100000.0,
                    "bid_size": 1.0,
                },
                {
                    "ask_price": 100600.0,
                    "ask_size": 2.0,
                    "bid_price": 99900.0,
                    "bid_size": 2.0,
                },
            ],
        }
        mock_get.return_value = mock_response
        
        snapshot = exchange.get_orderbook("BTC-KRW")
        
        assert snapshot.symbol == "BTC-KRW"
        assert len(snapshot.bids) > 0
        assert len(snapshot.asks) > 0
        assert snapshot.bids[0][0] == 100000.0  # 최상단 bid
        assert snapshot.asks[0][0] == 100500.0  # 최상단 ask

    @patch("requests.get")
    def test_get_orderbook_network_error(self, mock_get):
        """호가 조회 네트워크 에러"""
        config = {
            "api_key": "test_key",
            "api_secret": "test_secret",
            "base_url": "https://api.upbit.com",
            "timeout": 10,
        }
        
        exchange = UpbitSpotExchange(config)
        
        # Mock 네트워크 에러
        mock_get.side_effect = requests.exceptions.ConnectionError("Connection failed")
        
        with pytest.raises(NetworkError):
            exchange.get_orderbook("BTC-KRW")

    @patch("requests.get")
    def test_get_orderbook_empty_response(self, mock_get):
        """호가 조회 빈 응답"""
        config = {
            "api_key": "test_key",
            "api_secret": "test_secret",
            "base_url": "https://api.upbit.com",
            "timeout": 10,
        }
        
        exchange = UpbitSpotExchange(config)
        
        # Mock 빈 응답
        mock_response = Mock()
        mock_response.json.return_value = {
            "market": "BTC-KRW",
            "timestamp": 1234567890000,
            "orderbook_units": [],
        }
        mock_get.return_value = mock_response
        
        snapshot = exchange.get_orderbook("BTC-KRW")
        
        # 빈 호가도 처리 가능
        assert snapshot.symbol == "BTC-KRW"
        assert len(snapshot.bids) > 0  # 기본값 [(0, 0)]
        assert len(snapshot.asks) > 0

    def test_get_balance_no_api_key(self):
        """API 키 없을 때 잔고 조회"""
        config = {
            "api_key": "",
            "api_secret": "",
            "base_url": "https://api.upbit.com",
            "timeout": 10,
        }
        
        exchange = UpbitSpotExchange(config)
        
        with pytest.raises(AuthenticationError):
            exchange.get_balance()

    @patch("requests.get")
    def test_get_balance_success(self, mock_get):
        """잔고 조회 성공"""
        config = {
            "api_key": "test_key",
            "api_secret": "test_secret",
            "base_url": "https://api.upbit.com",
            "timeout": 10,
        }
        
        exchange = UpbitSpotExchange(config)
        
        # Mock 응답
        mock_response = Mock()
        mock_response.json.return_value = [
            {
                "currency": "KRW",
                "balance": "1000000",
                "locked": "0",
                "avg_buy_price": "0",
            },
            {
                "currency": "BTC",
                "balance": "1.5",
                "locked": "0",
                "avg_buy_price": "50000000",
            },
        ]
        mock_get.return_value = mock_response
        
        balances = exchange.get_balance()
        
        assert "KRW" in balances
        assert "BTC" in balances
        assert balances["KRW"].free == 1000000.0
        assert balances["BTC"].free == 1.5

    @patch("requests.get")
    def test_get_balance_network_error(self, mock_get):
        """잔고 조회 네트워크 에러"""
        config = {
            "api_key": "test_key",
            "api_secret": "test_secret",
            "base_url": "https://api.upbit.com",
            "timeout": 10,
        }
        
        exchange = UpbitSpotExchange(config)
        
        # Mock 네트워크 에러
        mock_get.side_effect = requests.exceptions.Timeout("Request timeout")
        
        with pytest.raises(NetworkError):
            exchange.get_balance()

    def test_create_order_live_disabled(self):
        """live_enabled=False일 때 주문 생성 금지"""
        config = {
            "api_key": "test_key",
            "api_secret": "test_secret",
            "base_url": "https://api.upbit.com",
            "timeout": 10,
            "live_enabled": False,
        }
        
        exchange = UpbitSpotExchange(config)
        
        from arbitrage.exchanges.base import OrderSide, OrderType
        
        with pytest.raises(RuntimeError) as exc_info:
            exchange.create_order(
                symbol="BTC-KRW",
                side=OrderSide.BUY,
                qty=0.01,
                price=100000.0,
                order_type=OrderType.LIMIT,
            )
        
        assert "Live trading is disabled" in str(exc_info.value)

    def test_cancel_order_live_disabled(self):
        """live_enabled=False일 때 주문 취소 금지"""
        config = {
            "api_key": "test_key",
            "api_secret": "test_secret",
            "base_url": "https://api.upbit.com",
            "timeout": 10,
            "live_enabled": False,
        }
        
        exchange = UpbitSpotExchange(config)
        
        with pytest.raises(RuntimeError) as exc_info:
            exchange.cancel_order("order_123")
        
        assert "Live trading is disabled" in str(exc_info.value)
