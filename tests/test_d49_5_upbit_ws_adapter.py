"""
D49.5: Upbit WebSocket Adapter 테스트

Upbit WebSocket 메시지 파싱 및 OrderbookSnapshot 변환을 검증한다.
"""

import pytest
from unittest.mock import Mock, AsyncMock
from typing import List

from arbitrage.exchanges.base import OrderBookSnapshot
from arbitrage.exchanges.upbit_ws_adapter import UpbitWebSocketAdapter


class TestD495UpbitWSAdapterBasics:
    """D49.5 Upbit WS 어댑터 기본 테스트"""
    
    def test_upbit_adapter_initialization(self):
        """Upbit 어댑터 초기화"""
        symbols = ["KRW-BTC", "KRW-ETH"]
        callback = Mock()
        
        adapter = UpbitWebSocketAdapter(symbols, callback)
        
        assert adapter.symbols == symbols
        assert adapter.callback == callback
        assert adapter.url == "wss://api.upbit.com/websocket/v1"
    
    def test_upbit_parse_orderbook_message(self):
        """Upbit orderbook 메시지 파싱"""
        callback = Mock()
        adapter = UpbitWebSocketAdapter(["KRW-BTC"], callback)
        
        message = {
            "type": "orderbook",
            "code": "KRW-BTC",
            "timestamp": 1710000000000,
            "orderbook_units": [
                {
                    "ask_price": 50100000,
                    "bid_price": 50000000,
                    "ask_size": 1.2,
                    "bid_size": 1.1,
                },
                {
                    "ask_price": 50200000,
                    "bid_price": 49900000,
                    "ask_size": 2.0,
                    "bid_size": 2.0,
                },
            ]
        }
        
        snapshot = adapter._parse_message(message)
        
        assert snapshot is not None
        assert snapshot.symbol == "KRW-BTC"
        assert snapshot.timestamp == 1710000000.0  # ms → s
        assert len(snapshot.bids) == 2
        assert len(snapshot.asks) == 2
        assert snapshot.bids[0] == (50000000.0, 1.1)
        assert snapshot.asks[0] == (50100000.0, 1.2)
    
    def test_upbit_parse_orderbook_max_10_levels(self):
        """Upbit orderbook 상위 10개 제한"""
        callback = Mock()
        adapter = UpbitWebSocketAdapter(["KRW-BTC"], callback)
        
        # 15개 호가 생성
        units = []
        for i in range(15):
            units.append({
                "ask_price": 50000000 + i * 1000,
                "bid_price": 49900000 - i * 1000,
                "ask_size": 1.0,
                "bid_size": 1.0,
            })
        
        message = {
            "type": "orderbook",
            "code": "KRW-BTC",
            "timestamp": 1710000000000,
            "orderbook_units": units,
        }
        
        snapshot = adapter._parse_message(message)
        
        assert snapshot is not None
        assert len(snapshot.bids) == 10  # 상위 10개만
        assert len(snapshot.asks) == 10
    
    def test_upbit_parse_missing_code(self):
        """Upbit 메시지: code 누락"""
        callback = Mock()
        adapter = UpbitWebSocketAdapter(["KRW-BTC"], callback)
        
        message = {
            "type": "orderbook",
            "timestamp": 1710000000000,
            "orderbook_units": [],
        }
        
        snapshot = adapter._parse_message(message)
        
        assert snapshot is None
    
    def test_upbit_parse_empty_units(self):
        """Upbit 메시지: orderbook_units 비어있음"""
        callback = Mock()
        adapter = UpbitWebSocketAdapter(["KRW-BTC"], callback)
        
        message = {
            "type": "orderbook",
            "code": "KRW-BTC",
            "timestamp": 1710000000000,
            "orderbook_units": [],
        }
        
        snapshot = adapter._parse_message(message)
        
        assert snapshot is None
    
    def test_upbit_parse_invalid_price(self):
        """Upbit 메시지: 잘못된 가격"""
        callback = Mock()
        adapter = UpbitWebSocketAdapter(["KRW-BTC"], callback)
        
        message = {
            "type": "orderbook",
            "code": "KRW-BTC",
            "timestamp": 1710000000000,
            "orderbook_units": [
                {
                    "ask_price": "invalid",
                    "bid_price": 50000000,
                    "ask_size": 1.0,
                    "bid_size": 1.0,
                },
            ]
        }
        
        snapshot = adapter._parse_message(message)
        
        # 파싱은 성공하지만, 잘못된 ask는 무시됨
        assert snapshot is not None
        assert len(snapshot.bids) == 1
        assert len(snapshot.asks) == 0  # invalid ask 무시
    
    def test_upbit_on_message_callback(self):
        """Upbit on_message 콜백"""
        callback = Mock()
        adapter = UpbitWebSocketAdapter(["KRW-BTC"], callback)
        
        message = {
            "type": "orderbook",
            "code": "KRW-BTC",
            "timestamp": 1710000000000,
            "orderbook_units": [
                {
                    "ask_price": 50100000,
                    "bid_price": 50000000,
                    "ask_size": 1.0,
                    "bid_size": 1.0,
                },
            ]
        }
        
        adapter.on_message(message)
        
        # 콜백 호출 확인
        callback.assert_called_once()
        snapshot = callback.call_args[0][0]
        assert isinstance(snapshot, OrderBookSnapshot)
        assert snapshot.symbol == "KRW-BTC"
    
    def test_upbit_get_latest_snapshot(self):
        """Upbit 최신 스냅샷 조회"""
        callback = Mock()
        adapter = UpbitWebSocketAdapter(["KRW-BTC"], callback)
        
        message = {
            "type": "orderbook",
            "code": "KRW-BTC",
            "timestamp": 1710000000000,
            "orderbook_units": [
                {
                    "ask_price": 50100000,
                    "bid_price": 50000000,
                    "ask_size": 1.0,
                    "bid_size": 1.0,
                },
            ]
        }
        
        adapter.on_message(message)
        
        # 최신 스냅샷 조회
        snapshot = adapter.get_latest_snapshot("KRW-BTC")
        assert snapshot is not None
        assert snapshot.symbol == "KRW-BTC"


class TestD495UpbitWSAdapterEdgeCases:
    """D49.5 Upbit WS 어댑터 엣지 케이스"""
    
    def test_upbit_parse_partial_units(self):
        """Upbit 메시지: 일부 필드 누락"""
        callback = Mock()
        adapter = UpbitWebSocketAdapter(["KRW-BTC"], callback)
        
        message = {
            "type": "orderbook",
            "code": "KRW-BTC",
            "timestamp": 1710000000000,
            "orderbook_units": [
                {
                    "ask_price": 50100000,
                    "ask_size": 1.0,
                    # bid 필드 누락
                },
                {
                    "bid_price": 50000000,
                    "bid_size": 1.0,
                    # ask 필드 누락
                },
            ]
        }
        
        snapshot = adapter._parse_message(message)
        
        assert snapshot is not None
        assert len(snapshot.bids) == 1
        assert len(snapshot.asks) == 1
    
    def test_upbit_timestamp_normalization(self):
        """Upbit 타임스탬프 정규화 (ms → s)"""
        callback = Mock()
        adapter = UpbitWebSocketAdapter(["KRW-BTC"], callback)
        
        message = {
            "type": "orderbook",
            "code": "KRW-BTC",
            "timestamp": 1710000000000,  # ms
            "orderbook_units": [
                {
                    "ask_price": 50100000,
                    "bid_price": 50000000,
                    "ask_size": 1.0,
                    "bid_size": 1.0,
                },
            ]
        }
        
        snapshot = adapter._parse_message(message)
        
        assert snapshot is not None
        assert snapshot.timestamp == 1710000000.0  # s
