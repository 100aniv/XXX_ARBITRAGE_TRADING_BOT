# -*- coding: utf-8 -*-
"""
D77-5: Upbit Rate Limit (429) 핸들링 테스트
"""

import pytest
from unittest.mock import Mock, patch, call
from arbitrage.exchanges.upbit_public_data import UpbitPublicDataClient


class TestUpbitRateLimit:
    """Upbit Rate Limit (429) 핸들링 테스트"""
    
    def test_fetch_ticker_rate_limit_retry_success(self):
        """429 에러 발생 후 재시도로 성공"""
        client = UpbitPublicDataClient(max_retries=3, backoff_base=0.01, backoff_max=0.05)
        
        # Mock response: 첫 2번은 429, 3번째는 200
        responses = [
            Mock(status_code=429),
            Mock(status_code=429),
            Mock(
                status_code=200,
                json=lambda: [
                    {
                        "market": "KRW-BTC",
                        "trade_price": 50000000.0,
                        "trade_volume": 1.5,
                        "acc_trade_volume_24h": 1000.0,
                        "acc_trade_price_24h": 50000000000.0,
                        "signed_change_rate": 0.02,
                    }
                ]
            ),
        ]
        
        with patch.object(client.session, 'get', side_effect=responses):
            ticker = client.fetch_ticker("KRW-BTC")
        
        # 검증: 최종 성공
        assert ticker is not None
        assert ticker.symbol == "KRW-BTC"
        assert ticker.trade_price == 50000000.0
        
        # Rate limit 히트 횟수 확인
        assert client.rate_limit_hits == 2
    
    def test_fetch_ticker_rate_limit_max_retries_exceeded(self):
        """429 에러가 최대 재시도 횟수를 초과"""
        client = UpbitPublicDataClient(max_retries=2, backoff_base=0.01, backoff_max=0.05)
        
        # Mock response: 계속 429
        mock_response = Mock(status_code=429)
        
        with patch.object(client.session, 'get', return_value=mock_response):
            ticker = client.fetch_ticker("KRW-BTC")
        
        # 검증: None 반환
        assert ticker is None
        
        # Rate limit 히트 횟수 확인 (max_retries + 1번 시도)
        assert client.rate_limit_hits == 3
    
    def test_fetch_orderbook_rate_limit_retry_success(self):
        """호가 조회 시 429 에러 발생 후 재시도로 성공"""
        client = UpbitPublicDataClient(max_retries=2, backoff_base=0.01, backoff_max=0.05)
        
        # Mock response: 첫 1번은 429, 2번째는 200
        responses = [
            Mock(status_code=429),
            Mock(
                status_code=200,
                json=lambda: [
                    {
                        "market": "KRW-BTC",
                        "timestamp": 1638316800000,
                        "orderbook_units": [
                            {"bid_price": 49000000.0, "bid_size": 0.5, "ask_price": 50000000.0, "ask_size": 0.3},
                        ]
                    }
                ]
            ),
        ]
        
        with patch.object(client.session, 'get', side_effect=responses):
            orderbook = client.fetch_orderbook("KRW-BTC")
        
        # 검증: 최종 성공
        assert orderbook is not None
        assert orderbook.symbol == "KRW-BTC"
        assert len(orderbook.bids) == 1
        assert len(orderbook.asks) == 1
        
        # Rate limit 히트 횟수 확인
        assert client.rate_limit_hits == 1
    
    def test_fetch_top_symbols_rate_limit_on_market_all(self):
        """Top symbols 조회 시 market/all에서 429 발생"""
        client = UpbitPublicDataClient(max_retries=1, backoff_base=0.01, backoff_max=0.05)
        
        # Mock response: market/all에서 429, 재시도 시 200
        responses = [
            Mock(status_code=429),
            Mock(
                status_code=200,
                json=lambda: [
                    {"market": "KRW-BTC"},
                    {"market": "KRW-ETH"},
                ]
            ),
            # ticker 요청
            Mock(
                status_code=200,
                json=lambda: [
                    {"market": "KRW-BTC", "acc_trade_price_24h": 1000000000.0},
                    {"market": "KRW-ETH", "acc_trade_price_24h": 500000000.0},
                ]
            ),
        ]
        
        with patch.object(client.session, 'get', side_effect=responses):
            symbols = client.fetch_top_symbols(limit=2)
        
        # 검증: 최종 성공
        assert len(symbols) == 2
        assert "KRW-BTC" in symbols
        assert "KRW-ETH" in symbols
        
        # Rate limit 히트 횟수 확인
        assert client.rate_limit_hits == 1
    
    def test_fetch_top_symbols_rate_limit_on_ticker(self):
        """Top symbols 조회 시 ticker에서 429 발생"""
        client = UpbitPublicDataClient(max_retries=1, backoff_base=0.01, backoff_max=0.05)
        
        # Mock response: market/all은 200, ticker에서 429 후 200
        responses = [
            Mock(
                status_code=200,
                json=lambda: [
                    {"market": "KRW-BTC"},
                    {"market": "KRW-ETH"},
                ]
            ),
            # ticker 첫 요청: 429
            Mock(status_code=429),
            # ticker 재시도: 200
            Mock(
                status_code=200,
                json=lambda: [
                    {"market": "KRW-BTC", "acc_trade_price_24h": 1000000000.0},
                    {"market": "KRW-ETH", "acc_trade_price_24h": 500000000.0},
                ]
            ),
        ]
        
        with patch.object(client.session, 'get', side_effect=responses):
            symbols = client.fetch_top_symbols(limit=2)
        
        # 검증: 최종 성공
        assert len(symbols) == 2
        
        # Rate limit 히트 횟수 확인
        assert client.rate_limit_hits == 1
    
    def test_backoff_time_calculation(self):
        """Exponential backoff 시간 계산"""
        client = UpbitPublicDataClient(max_retries=5, backoff_base=0.5, backoff_max=4.0)
        
        # Mock response: 계속 429
        mock_response = Mock(status_code=429)
        
        with patch.object(client.session, 'get', return_value=mock_response), \
                patch('arbitrage.exchanges.upbit_public_data.time.sleep') as mock_sleep:
            ticker = client.fetch_ticker("KRW-BTC")
        
        # 검증: None 반환
        assert ticker is None
        
        # 검증: backoff 시퀀스 확인
        expected_calls = [
            call(0.5),
            call(1.0),
            call(2.0),
            call(4.0),
            call(4.0),
        ]
        assert mock_sleep.call_args_list == expected_calls
    
    def test_request_exception_retry(self):
        """RequestException 발생 시 재시도"""
        import requests
        client = UpbitPublicDataClient(max_retries=2, backoff_base=0.01, backoff_max=0.05)
        
        # Mock: 첫 1번은 ConnectionError, 2번째는 200
        responses = [
            requests.exceptions.ConnectionError("Connection failed"),
            Mock(
                status_code=200,
                json=lambda: [
                    {
                        "market": "KRW-BTC",
                        "trade_price": 50000000.0,
                        "trade_volume": 1.5,
                        "acc_trade_volume_24h": 1000.0,
                        "acc_trade_price_24h": 50000000000.0,
                        "signed_change_rate": 0.02,
                    }
                ]
            ),
        ]
        
        with patch.object(client.session, 'get', side_effect=responses):
            ticker = client.fetch_ticker("KRW-BTC")
        
        # 검증: 최종 성공
        assert ticker is not None
        assert ticker.symbol == "KRW-BTC"
