"""
D49.5: Binance WebSocket Adapter 테스트

Binance WebSocket 메시지 파싱 및 OrderbookSnapshot 변환을 검증한다.
"""

import pytest
from unittest.mock import Mock, AsyncMock
from typing import List

from arbitrage.exchanges.base import OrderBookSnapshot
from arbitrage.exchanges.binance_ws_adapter import BinanceWebSocketAdapter


class TestD495BinanceWSAdapterBasics:
    """D49.5 Binance WS 어댑터 기본 테스트"""
    
    def test_binance_adapter_initialization(self):
        """Binance 어댑터 초기화"""
        symbols = ["btcusdt", "ethusdt"]
        callback = Mock()
        
        adapter = BinanceWebSocketAdapter(symbols, callback)
        
        assert adapter.symbols == symbols
        assert adapter.callback == callback
        assert adapter.url == "wss://fstream.binance.com/stream"
        assert adapter.depth == "20"
        assert adapter.interval == "100ms"
    
    def test_binance_parse_depth_message(self):
        """Binance depth 메시지 파싱"""
        callback = Mock()
        adapter = BinanceWebSocketAdapter(["btcusdt"], callback)
        
        message = {
            "stream": "btcusdt@depth20@100ms",
            "data": {
                "E": 1710000000000,
                "b": [
                    ["50000.0", "1.0"],
                    ["49999.0", "2.0"],
                ],
                "a": [
                    ["50001.0", "1.0"],
                    ["50002.0", "2.0"],
                ],
            }
        }
        
        snapshot = adapter._parse_message(message)
        
        assert snapshot is not None
        assert snapshot.symbol == "BTCUSDT"
        assert snapshot.timestamp == 1710000000.0  # ms → s
        assert len(snapshot.bids) == 2
        assert len(snapshot.asks) == 2
        assert snapshot.bids[0] == (50000.0, 1.0)
        assert snapshot.asks[0] == (50001.0, 1.0)
    
    def test_binance_parse_depth_max_20_levels(self):
        """Binance depth 상위 20개 제한"""
        callback = Mock()
        adapter = BinanceWebSocketAdapter(["btcusdt"], callback)
        
        # 30개 호가 생성
        bids = [[str(50000.0 - i), "1.0"] for i in range(30)]
        asks = [[str(50001.0 + i), "1.0"] for i in range(30)]
        
        message = {
            "stream": "btcusdt@depth20@100ms",
            "data": {
                "E": 1710000000000,
                "b": bids,
                "a": asks,
            }
        }
        
        snapshot = adapter._parse_message(message)
        
        assert snapshot is not None
        assert len(snapshot.bids) == 20  # 상위 20개만
        assert len(snapshot.asks) == 20
    
    def test_binance_parse_symbol_extraction(self):
        """Binance stream에서 symbol 추출"""
        callback = Mock()
        adapter = BinanceWebSocketAdapter(["btcusdt"], callback)
        
        message = {
            "stream": "btcusdt@depth20@100ms",
            "data": {
                "E": 1710000000000,
                "b": [["50000.0", "1.0"]],
                "a": [["50001.0", "1.0"]],
            }
        }
        
        snapshot = adapter._parse_message(message)
        
        assert snapshot is not None
        assert snapshot.symbol == "BTCUSDT"  # 대문자 변환
    
    def test_binance_parse_missing_stream(self):
        """Binance 메시지: stream 누락"""
        callback = Mock()
        adapter = BinanceWebSocketAdapter(["btcusdt"], callback)
        
        message = {
            "data": {
                "E": 1710000000000,
                "b": [["50000.0", "1.0"]],
                "a": [["50001.0", "1.0"]],
            }
        }
        
        snapshot = adapter._parse_message(message)
        
        assert snapshot is None
    
    def test_binance_parse_missing_data(self):
        """Binance 메시지: data 누락"""
        callback = Mock()
        adapter = BinanceWebSocketAdapter(["btcusdt"], callback)
        
        message = {
            "stream": "btcusdt@depth20@100ms",
        }
        
        snapshot = adapter._parse_message(message)
        
        assert snapshot is None
    
    def test_binance_parse_empty_bids_asks(self):
        """Binance 메시지: bids/asks 비어있음"""
        callback = Mock()
        adapter = BinanceWebSocketAdapter(["btcusdt"], callback)
        
        message = {
            "stream": "btcusdt@depth20@100ms",
            "data": {
                "E": 1710000000000,
                "b": [],
                "a": [],
            }
        }
        
        snapshot = adapter._parse_message(message)
        
        assert snapshot is None
    
    def test_binance_parse_invalid_price(self):
        """Binance 메시지: 잘못된 가격"""
        callback = Mock()
        adapter = BinanceWebSocketAdapter(["btcusdt"], callback)
        
        message = {
            "stream": "btcusdt@depth20@100ms",
            "data": {
                "E": 1710000000000,
                "b": [["invalid", "1.0"], ["50000.0", "1.0"]],
                "a": [["50001.0", "1.0"]],
            }
        }
        
        snapshot = adapter._parse_message(message)
        
        # 파싱은 성공하지만, 잘못된 bid는 무시됨
        assert snapshot is not None
        assert len(snapshot.bids) == 1  # 유효한 bid만
        assert len(snapshot.asks) == 1
    
    def test_binance_on_message_callback(self):
        """Binance on_message 콜백"""
        callback = Mock()
        adapter = BinanceWebSocketAdapter(["btcusdt"], callback)
        
        message = {
            "stream": "btcusdt@depth20@100ms",
            "data": {
                "E": 1710000000000,
                "b": [["50000.0", "1.0"]],
                "a": [["50001.0", "1.0"]],
            }
        }
        
        adapter.on_message(message)
        
        # 콜백 호출 확인
        callback.assert_called_once()
        snapshot = callback.call_args[0][0]
        assert isinstance(snapshot, OrderBookSnapshot)
        assert snapshot.symbol == "BTCUSDT"
    
    def test_binance_get_latest_snapshot(self):
        """Binance 최신 스냅샷 조회"""
        callback = Mock()
        adapter = BinanceWebSocketAdapter(["btcusdt"], callback)
        
        message = {
            "stream": "btcusdt@depth20@100ms",
            "data": {
                "E": 1710000000000,
                "b": [["50000.0", "1.0"]],
                "a": [["50001.0", "1.0"]],
            }
        }
        
        adapter.on_message(message)
        
        # 최신 스냅샷 조회
        snapshot = adapter.get_latest_snapshot("BTCUSDT")
        assert snapshot is not None
        assert snapshot.symbol == "BTCUSDT"


class TestD495BinanceWSAdapterEdgeCases:
    """D49.5 Binance WS 어댑터 엣지 케이스"""
    
    def test_binance_timestamp_normalization(self):
        """Binance 타임스탬프 정규화 (ms → s)"""
        callback = Mock()
        adapter = BinanceWebSocketAdapter(["btcusdt"], callback)
        
        message = {
            "stream": "btcusdt@depth20@100ms",
            "data": {
                "E": 1710000000000,  # ms
                "b": [["50000.0", "1.0"]],
                "a": [["50001.0", "1.0"]],
            }
        }
        
        snapshot = adapter._parse_message(message)
        
        assert snapshot is not None
        assert snapshot.timestamp == 1710000000.0  # s
    
    def test_binance_custom_depth_interval(self):
        """Binance 사용자 정의 depth/interval"""
        callback = Mock()
        adapter = BinanceWebSocketAdapter(
            ["btcusdt"],
            callback,
            depth="10",
            interval="500ms",
        )
        
        assert adapter.depth == "10"
        assert adapter.interval == "500ms"
    
    def test_binance_multiple_symbols(self):
        """Binance 여러 심볼"""
        callback = Mock()
        adapter = BinanceWebSocketAdapter(
            ["btcusdt", "ethusdt"],
            callback,
        )
        
        # BTC 메시지
        btc_message = {
            "stream": "btcusdt@depth20@100ms",
            "data": {
                "E": 1710000000000,
                "b": [["50000.0", "1.0"]],
                "a": [["50001.0", "1.0"]],
            }
        }
        
        # ETH 메시지
        eth_message = {
            "stream": "ethusdt@depth20@100ms",
            "data": {
                "E": 1710000000000,
                "b": [["3000.0", "1.0"]],
                "a": [["3001.0", "1.0"]],
            }
        }
        
        adapter.on_message(btc_message)
        adapter.on_message(eth_message)
        
        # 각각 조회
        btc_snapshot = adapter.get_latest_snapshot("BTCUSDT")
        eth_snapshot = adapter.get_latest_snapshot("ETHUSDT")
        
        assert btc_snapshot is not None
        assert btc_snapshot.symbol == "BTCUSDT"
        assert eth_snapshot is not None
        assert eth_snapshot.symbol == "ETHUSDT"
