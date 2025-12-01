# -*- coding: utf-8 -*-
"""
D77-0-RM: Public Data Clients Tests

Upbit/Binance Public Data Clients 테스트.
실제 HTTP 호출은 mock 처리하여 빠른 unit test 수행.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from arbitrage.exchanges.upbit_public_data import (
    UpbitPublicDataClient,
    TickerInfo,
    OrderbookData,
    OrderbookLevel,
)
from arbitrage.exchanges.binance_public_data import (
    BinancePublicDataClient,
    BinanceTickerInfo,
    BinanceOrderbookData,
    BinanceOrderbookLevel,
)


class TestUpbitPublicDataClient:
    """Upbit Public Data Client 테스트"""
    
    def test_fetch_ticker_success(self):
        """티커 조회 성공"""
        client = UpbitPublicDataClient()
        
        # Mock response
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = [{
            "market": "KRW-BTC",
            "trade_price": 50000000.0,
            "trade_volume": 0.5,
            "acc_trade_volume_24h": 100.0,
            "acc_trade_price_24h": 5000000000.0,
            "signed_change_rate": 0.05,
        }]
        
        with patch.object(client.session, 'get', return_value=mock_resp):
            ticker = client.fetch_ticker("KRW-BTC")
        
        assert ticker is not None
        assert ticker.symbol == "KRW-BTC"
        assert ticker.trade_price == 50000000.0
        assert ticker.change_rate == 0.05
    
    def test_fetch_ticker_empty_response(self):
        """티커 조회 빈 응답"""
        client = UpbitPublicDataClient()
        
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = []
        
        with patch.object(client.session, 'get', return_value=mock_resp):
            ticker = client.fetch_ticker("KRW-BTC")
        
        assert ticker is None
    
    def test_fetch_orderbook_success(self):
        """호가 조회 성공"""
        client = UpbitPublicDataClient()
        
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = [{
            "market": "KRW-BTC",
            "timestamp": 1234567890000,
            "orderbook_units": [
                {"bid_price": 49990000.0, "bid_size": 0.1, "ask_price": 50010000.0, "ask_size": 0.2},
                {"bid_price": 49980000.0, "bid_size": 0.15, "ask_price": 50020000.0, "ask_size": 0.25},
            ]
        }]
        
        with patch.object(client.session, 'get', return_value=mock_resp):
            orderbook = client.fetch_orderbook("KRW-BTC")
        
        assert orderbook is not None
        assert orderbook.symbol == "KRW-BTC"
        assert len(orderbook.bids) == 2
        assert len(orderbook.asks) == 2
        assert orderbook.bids[0].price == 49990000.0
        assert orderbook.asks[0].price == 50010000.0
    
    def test_fetch_top_symbols_success(self):
        """Top symbols 조회 성공"""
        client = UpbitPublicDataClient()
        
        # Mock market/all
        mock_market_resp = Mock()
        mock_market_resp.status_code = 200
        mock_market_resp.json.return_value = [
            {"market": "KRW-BTC"},
            {"market": "KRW-ETH"},
            {"market": "KRW-XRP"},
            {"market": "BTC-ETH"},  # Should be filtered out
        ]
        
        # Mock ticker
        mock_ticker_resp = Mock()
        mock_ticker_resp.status_code = 200
        mock_ticker_resp.json.return_value = [
            {"market": "KRW-BTC", "acc_trade_price_24h": 1000.0},
            {"market": "KRW-ETH", "acc_trade_price_24h": 500.0},
            {"market": "KRW-XRP", "acc_trade_price_24h": 200.0},
        ]
        
        with patch.object(client.session, 'get') as mock_get:
            mock_get.side_effect = [mock_market_resp, mock_ticker_resp]
            symbols = client.fetch_top_symbols(market="KRW", limit=2)
        
        assert len(symbols) == 2
        assert symbols[0] == "KRW-BTC"  # Highest volume
        assert symbols[1] == "KRW-ETH"


class TestBinancePublicDataClient:
    """Binance Public Data Client 테스트"""
    
    def test_fetch_ticker_success(self):
        """티커 조회 성공"""
        client = BinancePublicDataClient()
        
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "symbol": "BTCUSDT",
            "lastPrice": "45000.0",
            "volume": "1000.0",
            "quoteVolume": "45000000.0",
            "priceChangePercent": "2.5",
        }
        
        with patch.object(client.session, 'get', return_value=mock_resp):
            ticker = client.fetch_ticker("BTCUSDT")
        
        assert ticker is not None
        assert ticker.symbol == "BTCUSDT"
        assert ticker.last_price == 45000.0
        assert ticker.price_change_percent == 2.5
    
    def test_fetch_orderbook_success(self):
        """호가 조회 성공"""
        client = BinancePublicDataClient()
        
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "bids": [["44990.0", "0.5"], ["44980.0", "0.6"]],
            "asks": [["45010.0", "0.3"], ["45020.0", "0.4"]],
        }
        
        with patch.object(client.session, 'get', return_value=mock_resp):
            orderbook = client.fetch_orderbook("BTCUSDT")
        
        assert orderbook is not None
        assert orderbook.symbol == "BTCUSDT"
        assert len(orderbook.bids) == 2
        assert len(orderbook.asks) == 2
        assert orderbook.bids[0].price == 44990.0
        assert orderbook.asks[0].price == 45010.0
    
    def test_fetch_top_symbols_success(self):
        """Top symbols 조회 성공"""
        client = BinancePublicDataClient()
        
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = [
            {"symbol": "BTCUSDT", "quoteVolume": "1000000.0"},
            {"symbol": "ETHUSDT", "quoteVolume": "500000.0"},
            {"symbol": "XRPUSDT", "quoteVolume": "200000.0"},
            {"symbol": "BTCBUSD", "quoteVolume": "100000.0"},  # Should be filtered out
        ]
        
        with patch.object(client.session, 'get', return_value=mock_resp):
            symbols = client.fetch_top_symbols(quote_asset="USDT", limit=2)
        
        assert len(symbols) == 2
        assert symbols[0] == "BTCUSDT"  # Highest volume
        assert symbols[1] == "ETHUSDT"
    
    def test_fetch_ticker_network_error(self):
        """네트워크 오류 처리"""
        import requests
        client = BinancePublicDataClient()
        
        with patch.object(client.session, 'get', side_effect=requests.exceptions.RequestException("Network error")):
            ticker = client.fetch_ticker("BTCUSDT")
        
        assert ticker is None


class TestPublicDataIntegration:
    """Public Data Clients 통합 테스트 (선택적)"""
    
    @pytest.mark.skip(reason="Real network call - run manually if needed")
    def test_upbit_real_fetch_ticker(self):
        """실제 Upbit API 호출 (수동 실행)"""
        client = UpbitPublicDataClient()
        ticker = client.fetch_ticker("KRW-BTC")
        
        assert ticker is not None
        assert ticker.symbol == "KRW-BTC"
        assert ticker.trade_price > 0
        
        client.close()
    
    @pytest.mark.skip(reason="Real network call - run manually if needed")
    def test_binance_real_fetch_ticker(self):
        """실제 Binance API 호출 (수동 실행)"""
        client = BinancePublicDataClient()
        ticker = client.fetch_ticker("BTCUSDT")
        
        assert ticker is not None
        assert ticker.symbol == "BTCUSDT"
        assert ticker.last_price > 0
        
        client.close()
