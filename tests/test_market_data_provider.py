"""
D202-1: MarketData Provider 테스트

테스트 범위:
- RestProvider: ticker/orderbook/trades contract
- WsProvider: L2 orderbook 파싱 contract
- Redis cache: TTL 100ms 검증
- Reconnect: 3회 실패 시 예외, backoff 증가
- Rate limit: endpoint별 카운터/차단
"""

import asyncio
import pytest
import time
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock
import fakeredis

from arbitrage.v2.marketdata.interfaces import (
    Ticker,
    Orderbook,
    OrderbookLevel,
    Trade,
)
from arbitrage.v2.marketdata.rest.upbit import UpbitRestProvider
from arbitrage.v2.marketdata.rest.binance import BinanceRestProvider
from arbitrage.v2.marketdata.ws.upbit import UpbitWsProvider
from arbitrage.v2.marketdata.ws.binance import BinanceWsProvider
from arbitrage.v2.marketdata.cache import MarketDataCache
from arbitrage.v2.marketdata.ratelimit import RateLimitCounter


class TestRestProviderContract:
    """RestProvider 계약 테스트 (ticker/orderbook/trades)"""
    
    @patch('arbitrage.v2.marketdata.rest.upbit.UpbitRestProvider.get_orderbook')
    @patch('requests.Session.get')
    def test_upbit_ticker_contract(self, mock_get, mock_orderbook):
        """Upbit ticker 응답 파싱 contract (D205-14-5: orderbook 기반)"""
        # Mock orderbook response (D205-14-5: get_ticker가 get_orderbook 호출)
        mock_orderbook_obj = Orderbook(
            exchange="upbit",
            symbol="BTC/KRW",
            bids=[OrderbookLevel(price=50000000.0, quantity=0.5)],
            asks=[OrderbookLevel(price=50100000.0, quantity=0.3)],
            timestamp=datetime.now(),
        )
        mock_orderbook.return_value = mock_orderbook_obj
        
        # Mock ticker API response (volume만 사용)
        mock_resp = Mock()
        mock_resp.json.return_value = [{
            "trade_price": 50000000.0,
            "acc_trade_volume_24h": 123.45,
        }]
        mock_resp.raise_for_status = Mock()
        mock_get.return_value = mock_resp
        
        # Execute
        provider = UpbitRestProvider()
        ticker = provider.get_ticker("BTC/KRW")
        
        # Assert contract
        assert ticker is not None
        assert ticker.exchange == "upbit"
        assert ticker.symbol == "BTC/KRW"
        assert ticker.bid == 50000000.0
        assert ticker.ask == 50100000.0  # D205-14-5: orderbook에서 가져옴
        assert ticker.volume == 123.45
        assert isinstance(ticker.timestamp, datetime)
        # D205-14-5: size 필드 검증
        assert ticker.bid_size == 0.5
        assert ticker.ask_size == 0.3
    
    @patch('requests.Session.get')
    def test_binance_ticker_contract(self, mock_get):
        """Binance ticker 응답 파싱 contract"""
        # Mock response (D205-14-5: size 필드 추가)
        mock_resp = Mock()
        mock_resp.json.return_value = {
            "bidPrice": "50000.0",
            "askPrice": "50100.0",
            "bidQty": "0.5",
            "askQty": "0.3",
        }
        mock_resp.raise_for_status = Mock()
        mock_get.return_value = mock_resp
        
        # Execute (D205-14-6: 테스트는 Spot API 사용)
        provider = BinanceRestProvider(market_type="spot")
        ticker = provider.get_ticker("BTC/USDT")
        
        # Assert contract
        assert ticker is not None
        assert ticker.exchange == "binance"
        assert ticker.symbol == "BTC/USDT"
        assert ticker.bid == 50000.0
        assert ticker.ask == 50100.0
    
    @patch('requests.Session.get')
    def test_upbit_orderbook_contract(self, mock_get):
        """Upbit orderbook 응답 파싱 contract"""
        # Mock response
        mock_resp = Mock()
        mock_resp.json.return_value = [{
            "orderbook_units": [
                {"bid_price": 50000000.0, "bid_size": 0.5, "ask_price": 50100000.0, "ask_size": 0.3},
                {"bid_price": 49990000.0, "bid_size": 1.2, "ask_price": 50110000.0, "ask_size": 0.8},
            ]
        }]
        mock_resp.raise_for_status = Mock()
        mock_get.return_value = mock_resp
        
        # Execute
        provider = UpbitRestProvider()
        orderbook = provider.get_orderbook("BTC/KRW", depth=2)
        
        # Assert contract
        assert orderbook is not None
        assert orderbook.exchange == "upbit"
        assert orderbook.symbol == "BTC/KRW"
        assert len(orderbook.bids) == 2
        assert len(orderbook.asks) == 2
        assert orderbook.bids[0].price == 50000000.0
        assert orderbook.bids[0].quantity == 0.5
        assert orderbook.asks[0].price == 50100000.0
        assert orderbook.asks[0].quantity == 0.3
    
    @patch('requests.Session.get')
    def test_binance_orderbook_contract(self, mock_get):
        """Binance orderbook 응답 파싱 contract"""
        # Mock response
        mock_resp = Mock()
        mock_resp.json.return_value = {
            "bids": [["50000.0", "0.5"], ["49990.0", "1.2"]],
            "asks": [["50100.0", "0.3"], ["50110.0", "0.8"]],
        }
        mock_resp.raise_for_status = Mock()
        mock_get.return_value = mock_resp
        
        # Execute (D205-14-6: 테스트는 Spot API 사용)
        provider = BinanceRestProvider(market_type="spot")
        orderbook = provider.get_orderbook("BTC/USDT", depth=2)
        
        # Assert contract
        assert orderbook is not None
        assert orderbook.exchange == "binance"
        assert orderbook.symbol == "BTC/USDT"
        assert len(orderbook.bids) == 2
        assert len(orderbook.asks) == 2
        assert orderbook.bids[0].price == 50000.0
        assert orderbook.asks[0].price == 50100.0
    
    @patch('requests.Session.get')
    def test_upbit_trades_contract(self, mock_get):
        """Upbit trades 응답 파싱 contract"""
        # Mock response
        mock_resp = Mock()
        mock_resp.json.return_value = [
            {
                "trade_date_utc": "2025-12-29",
                "trade_time_utc": "12:00:00",
                "trade_price": 50000000.0,
                "trade_volume": 0.1,
                "ask_bid": "BID",
            }
        ]
        mock_resp.raise_for_status = Mock()
        mock_get.return_value = mock_resp
        
        # Execute
        provider = UpbitRestProvider()
        trades = provider.get_trades("BTC/KRW", limit=1)
        
        # Assert contract
        assert len(trades) == 1
        assert trades[0].exchange == "upbit"
        assert trades[0].symbol == "BTC/KRW"
        assert trades[0].price == 50000000.0
        assert trades[0].quantity == 0.1
        assert trades[0].side == "buy"  # BID → buy
    
    @patch('requests.Session.get')
    def test_binance_trades_contract(self, mock_get):
        """Binance trades 응답 파싱 contract"""
        # Mock response
        mock_resp = Mock()
        import time as time_module
        current_timestamp_ms = int(time_module.time() * 1000)
        mock_resp.json.return_value = [
            {
                "time": current_timestamp_ms,
                "price": "50000.0",
                "qty": "0.1",
                "isBuyerMaker": True,
            }
        ]
        mock_resp.raise_for_status = Mock()
        mock_get.return_value = mock_resp
        
        # Execute (D205-14-6: 테스트는 Spot API 사용)
        provider = BinanceRestProvider(market_type="spot")
        trades = provider.get_trades("BTC/USDT", limit=1)
        
        # Assert contract
        assert len(trades) == 1
        assert trades[0].exchange == "binance"
        assert trades[0].symbol == "BTC/USDT"
        assert trades[0].price == 50000.0
        assert trades[0].quantity == 0.1
        assert trades[0].side == "sell"  # isBuyerMaker=True → sell


class TestWsProviderContract:
    """WsProvider 계약 테스트 (L2 orderbook, reconnect)"""
    
    @pytest.mark.asyncio
    async def test_upbit_ws_connect_disconnect(self):
        """Upbit WS 연결/종료 contract"""
        provider = UpbitWsProvider()
        
        # Connect
        await provider.connect()
        assert await provider.health_check() is True
        
        # Disconnect
        await provider.disconnect()
        assert await provider.health_check() is False
    
    @pytest.mark.asyncio
    async def test_binance_ws_connect_disconnect(self):
        """Binance WS 연결/종료 contract"""
        provider = BinanceWsProvider()
        
        # Connect
        await provider.connect()
        assert await provider.health_check() is True
        
        # Disconnect
        await provider.disconnect()
        assert await provider.health_check() is False
    
    @pytest.mark.asyncio
    async def test_upbit_ws_subscribe(self):
        """Upbit WS 구독 contract"""
        provider = UpbitWsProvider()
        await provider.connect()
        
        # Subscribe
        await provider.subscribe(["BTC/KRW", "ETH/KRW"])
        
        # No exception = success
        assert True
    
    @pytest.mark.asyncio
    async def test_upbit_ws_reconnect_max_attempts(self):
        """Upbit WS reconnect 최대 3회 실패 시 False 반환"""
        provider = UpbitWsProvider(max_reconnect_attempts=3, reconnect_backoff=0.01)
        provider._is_connected = False
        
        # Mock connect to always fail
        async def mock_connect_fail():
            raise Exception("Connection failed")
        
        provider.connect = mock_connect_fail
        
        # Execute reconnect
        result = await provider._reconnect()
        
        # Assert: 3회 실패 후 False 반환
        assert result is False
        assert provider._reconnect_count == 3
    
    @pytest.mark.asyncio
    async def test_binance_ws_reconnect_backoff(self):
        """Binance WS reconnect backoff 증가 검증 (Mock asyncio.sleep)"""
        from unittest.mock import AsyncMock, patch
        
        provider = BinanceWsProvider(max_reconnect_attempts=2, reconnect_backoff=2.0)
        provider._is_connected = False
        
        # Mock connect to succeed on 2nd attempt
        connect_count = 0
        async def mock_connect_retry():
            nonlocal connect_count
            connect_count += 1
            if connect_count == 1:
                raise Exception("First attempt failed")
            else:
                provider._is_connected = True
        
        provider.connect = mock_connect_retry
        
        # Patch asyncio.sleep to verify backoff timing
        with patch('asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
            result = await provider._reconnect()
            
            # Assert: 첫 실패 후 재시도(count=2), 두 번째는 성공
            assert result is True
            assert provider._reconnect_count == 2
            # sleep은 2번 호출 (2^1=2s, 2^2=4s)
            assert mock_sleep.call_count == 2
            mock_sleep.assert_any_call(2.0)  # 첫 재시도
            mock_sleep.assert_any_call(4.0)  # 두 번째 재시도


class TestMarketDataCache:
    """Redis cache 테스트 (TTL 100ms)"""
    
    def test_ticker_cache_ttl(self):
        """Ticker cache PSETEX 호출 검증 (Mock Redis)"""
        from unittest.mock import MagicMock
        
        mock_redis = MagicMock()
        cache = MarketDataCache(mock_redis, env="test", run_id="cache_test", ttl_ms=100)
        
        # Set ticker
        ticker = Ticker(
            exchange="upbit",
            symbol="BTC/KRW",
            timestamp=datetime.now(),
            bid=50000000.0,
            ask=50100000.0,
            last=50050000.0,
            volume=123.45,
        )
        cache.set_ticker(ticker)
        
        # Assert: PSETEX called with correct key, TTL (100ms), and JSON value
        assert mock_redis.psetex.called
        call_args = mock_redis.psetex.call_args
        key, ttl_ms, value = call_args[0]
        
        assert key == "v2:test:cache_test:market:upbit:BTC/KRW:ticker"
        assert ttl_ms == 100
        assert "50000000.0" in value  # JSON serialized bid
    
    def test_orderbook_cache_ttl(self):
        """Orderbook cache PSETEX 호출 검증 (Mock Redis)"""
        from unittest.mock import MagicMock
        
        mock_redis = MagicMock()
        cache = MarketDataCache(mock_redis, env="test", run_id="cache_test", ttl_ms=100)
        
        # Set orderbook
        orderbook = Orderbook(
            exchange="binance",
            symbol="BTC/USDT",
            timestamp=datetime.now(),
            bids=[OrderbookLevel(price=50000.0, quantity=0.5)],
            asks=[OrderbookLevel(price=50100.0, quantity=0.3)],
        )
        cache.set_orderbook(orderbook)
        
        # Assert: PSETEX called with correct key, TTL (100ms), and JSON value
        assert mock_redis.psetex.called
        call_args = mock_redis.psetex.call_args
        key, ttl_ms, value = call_args[0]
        
        assert key == "v2:test:cache_test:market:binance:BTC/USDT:orderbook"
        assert ttl_ms == 100
        assert "50000.0" in value  # JSON serialized bid price
    
    def test_redis_key_format_ssot(self):
        """Redis key 포맷 SSOT 규칙 준수 검증 (Mock Redis)"""
        from unittest.mock import MagicMock
        
        mock_redis = MagicMock()
        cache = MarketDataCache(mock_redis, env="prod", run_id="d202_1_test", ttl_ms=100)
        
        # Set ticker
        ticker = Ticker(
            exchange="upbit",
            symbol="BTC/KRW",
            timestamp=datetime.now(),
            bid=50000000.0,
            ask=50100000.0,
            last=50050000.0,
            volume=123.45,
        )
        cache.set_ticker(ticker)
        
        # Assert: PSETEX called with SSOT key format
        call_args = mock_redis.psetex.call_args
        key = call_args[0][0]
        
        expected_key = "v2:prod:d202_1_test:market:upbit:BTC/KRW:ticker"
        assert key == expected_key


class TestRateLimitCounter:
    """Rate limit counter 테스트 (endpoint별 카운터/차단)"""
    
    def test_rate_limit_allow(self):
        """Rate limit 허용 케이스 (limit 이하)"""
        redis_client = fakeredis.FakeStrictRedis(decode_responses=False)
        counter = RateLimitCounter(redis_client, env="test", run_id="ratelimit_test")
        
        # 1회 호출 (허용)
        allowed = counter.check("upbit", "orders")
        assert allowed is True
        
        # 현재 카운트 확인
        count = counter.get_current_count("upbit", "orders")
        assert count == 1
    
    def test_rate_limit_block(self):
        """Rate limit 차단 케이스 (limit 초과)"""
        redis_client = fakeredis.FakeStrictRedis(decode_responses=True)
        counter = RateLimitCounter(redis_client, env="test", run_id="ratelimit_test")
        
        # Upbit orders limit: 8 req/s
        # 8회까지 허용, 9회째 차단
        for i in range(8):
            allowed = counter.check("upbit", "orders")
            assert allowed is True
        
        # 9회째 차단
        blocked = counter.check("upbit", "orders")
        assert blocked is False
        
        # 카운트 확인
        count = counter.get_current_count("upbit", "orders")
        assert count == 9
    
    def test_rate_limit_ttl_reset(self):
        """Rate limit TTL 1s 후 리셋 검증"""
        redis_client = fakeredis.FakeStrictRedis(decode_responses=True)
        counter = RateLimitCounter(redis_client, env="test", run_id="ratelimit_test")
        
        # 1회 호출
        counter.check("binance", "market_data")
        count_before = counter.get_current_count("binance", "market_data")
        assert count_before == 1
        
        # Wait 1.1s (TTL 1s)
        time.sleep(1.1)
        
        # TTL 만료 후 카운트 리셋
        count_after = counter.get_current_count("binance", "market_data")
        assert count_after == 0
    
    def test_redis_key_format_ssot_ratelimit(self):
        """Rate limit Redis key 포맷 SSOT 규칙 준수"""
        redis_client = fakeredis.FakeStrictRedis(decode_responses=True)
        counter = RateLimitCounter(redis_client, env="prod", run_id="d202_1_test")
        
        # Check
        counter.check("upbit", "orders")
        
        # Key format: v2:{env}:{run_id}:ratelimit:{exchange}:{endpoint}
        expected_key = "v2:prod:d202_1_test:ratelimit:upbit:orders"
        assert expected_key in redis_client.keys()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
