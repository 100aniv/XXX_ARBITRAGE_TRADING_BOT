"""
D46: Binance Read-Only 어댑터 테스트

실제 API 호출 (mock 사용)을 통한 Binance 어댑터 검증
"""

import pytest
from unittest.mock import Mock, patch
import requests
from arbitrage.exchanges.binance_futures import BinanceFuturesExchange
from arbitrage.exchanges.exceptions import NetworkError, AuthenticationError


class TestD46BinanceAdapter:
    """D46 Binance Read-Only 어댑터 테스트"""

    def test_binance_initialization(self):
        """Binance 어댑터 초기화"""
        config = {
            "api_key": "test_key",
            "api_secret": "test_secret",
            "base_url": "https://fapi.binance.com",
            "timeout": 10,
            "leverage": 1,
            "live_enabled": False,
        }
        
        exchange = BinanceFuturesExchange(config)
        
        assert exchange.name == "binance_futures"
        assert exchange.api_key == "test_key"
        assert exchange.api_secret == "test_secret"
        assert exchange.leverage == 1
        assert exchange.live_enabled is False

    @patch("requests.get")
    def test_get_orderbook_success(self, mock_get):
        """호가 조회 성공"""
        config = {
            "api_key": "test_key",
            "api_secret": "test_secret",
            "base_url": "https://fapi.binance.com",
            "timeout": 10,
        }
        
        exchange = BinanceFuturesExchange(config)
        
        # Mock 응답
        mock_response = Mock()
        mock_response.json.return_value = {
            "bids": [
                ["40000", "1.0"],
                ["39999", "2.0"],
            ],
            "asks": [
                ["40100", "1.0"],
                ["40101", "2.0"],
            ],
            "E": 1234567890000,
            "T": 1234567890000,
        }
        mock_get.return_value = mock_response
        
        snapshot = exchange.get_orderbook("BTCUSDT")
        
        assert snapshot.symbol == "BTCUSDT"
        assert len(snapshot.bids) > 0
        assert len(snapshot.asks) > 0
        assert snapshot.bids[0][0] == 40000.0  # 최상단 bid
        assert snapshot.asks[0][0] == 40100.0  # 최상단 ask

    @patch("requests.get")
    def test_get_orderbook_network_error(self, mock_get):
        """호가 조회 네트워크 에러"""
        config = {
            "api_key": "test_key",
            "api_secret": "test_secret",
            "base_url": "https://fapi.binance.com",
            "timeout": 10,
        }
        
        exchange = BinanceFuturesExchange(config)
        
        # Mock 네트워크 에러
        mock_get.side_effect = requests.exceptions.ConnectionError("Connection failed")
        
        with pytest.raises(NetworkError):
            exchange.get_orderbook("BTCUSDT")

    @patch("requests.get")
    def test_get_orderbook_empty_response(self, mock_get):
        """호가 조회 빈 응답"""
        config = {
            "api_key": "test_key",
            "api_secret": "test_secret",
            "base_url": "https://fapi.binance.com",
            "timeout": 10,
        }
        
        exchange = BinanceFuturesExchange(config)
        
        # Mock 빈 응답
        mock_response = Mock()
        mock_response.json.return_value = {
            "bids": [],
            "asks": [],
            "E": 1234567890000,
            "T": 1234567890000,
        }
        mock_get.return_value = mock_response
        
        snapshot = exchange.get_orderbook("BTCUSDT")
        
        # 빈 호가도 처리 가능
        assert snapshot.symbol == "BTCUSDT"
        assert len(snapshot.bids) > 0  # 기본값 [(0, 0)]
        assert len(snapshot.asks) > 0

    def test_get_balance_no_api_key(self):
        """API 키 없을 때 잔고 조회"""
        config = {
            "api_key": "",
            "api_secret": "",
            "base_url": "https://fapi.binance.com",
            "timeout": 10,
        }
        
        exchange = BinanceFuturesExchange(config)
        
        with pytest.raises(AuthenticationError):
            exchange.get_balance()

    @patch("requests.get")
    def test_get_balance_success(self, mock_get):
        """잔고 조회 성공"""
        config = {
            "api_key": "test_key",
            "api_secret": "test_secret",
            "base_url": "https://fapi.binance.com",
            "timeout": 10,
        }
        
        exchange = BinanceFuturesExchange(config)
        
        # Mock 응답
        mock_response = Mock()
        mock_response.json.return_value = {
            "assets": [
                {
                    "asset": "USDT",
                    "walletBalance": "10000",
                    "marginBalance": "10000",
                    "unrealizedProfit": "0",
                },
                {
                    "asset": "BTC",
                    "walletBalance": "1.5",
                    "marginBalance": "1.5",
                    "unrealizedProfit": "0",
                },
            ],
            "positions": [],
        }
        mock_get.return_value = mock_response
        
        balances = exchange.get_balance()
        
        assert "USDT" in balances
        assert "BTC" in balances
        assert balances["USDT"].free == 10000.0
        assert balances["BTC"].free == 1.5

    @patch("requests.get")
    def test_get_balance_network_error(self, mock_get):
        """잔고 조회 네트워크 에러"""
        config = {
            "api_key": "test_key",
            "api_secret": "test_secret",
            "base_url": "https://fapi.binance.com",
            "timeout": 10,
        }
        
        exchange = BinanceFuturesExchange(config)
        
        # Mock 네트워크 에러
        mock_get.side_effect = requests.exceptions.Timeout("Request timeout")
        
        with pytest.raises(NetworkError):
            exchange.get_balance()

    def test_create_order_live_disabled(self):
        """live_enabled=False일 때 주문 생성 금지"""
        config = {
            "api_key": "test_key",
            "api_secret": "test_secret",
            "base_url": "https://fapi.binance.com",
            "timeout": 10,
            "live_enabled": False,
        }
        
        exchange = BinanceFuturesExchange(config)
        
        from arbitrage.exchanges.base import OrderSide, OrderType
        
        with pytest.raises(RuntimeError) as exc_info:
            exchange.create_order(
                symbol="BTCUSDT",
                side=OrderSide.BUY,
                qty=0.01,
                price=40000.0,
                order_type=OrderType.LIMIT,
            )
        
        assert "Live trading is disabled" in str(exc_info.value)

    def test_cancel_order_live_disabled(self):
        """live_enabled=False일 때 주문 취소 금지"""
        config = {
            "api_key": "test_key",
            "api_secret": "test_secret",
            "base_url": "https://fapi.binance.com",
            "timeout": 10,
            "live_enabled": False,
        }
        
        exchange = BinanceFuturesExchange(config)
        
        with pytest.raises(RuntimeError) as exc_info:
            exchange.cancel_order("order_123")
        
        assert "Live trading is disabled" in str(exc_info.value)
