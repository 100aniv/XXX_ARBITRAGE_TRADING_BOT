"""
D49: Market Data Provider 테스트

RestMarketDataProvider와 WebSocketMarketDataProvider의 기능을 검증한다.
"""

import pytest
from unittest.mock import Mock, MagicMock
from typing import Dict

from arbitrage.exchanges.base import OrderBookSnapshot
from arbitrage.exchanges.market_data_provider import (
    RestMarketDataProvider,
    WebSocketMarketDataProvider,
)


class TestD49RestMarketDataProvider:
    """D49 REST Market Data Provider 테스트"""
    
    def test_rest_provider_initialization(self):
        """REST 제공자 초기화"""
        exchanges = {
            "a": Mock(),
            "b": Mock(),
        }
        
        provider = RestMarketDataProvider(exchanges)
        
        assert provider.exchanges == exchanges
        assert provider._is_running is False
    
    def test_rest_provider_start_stop(self):
        """REST 제공자 시작/종료"""
        exchanges = {"a": Mock(), "b": Mock()}
        provider = RestMarketDataProvider(exchanges)
        
        provider.start()
        assert provider._is_running is True
        
        provider.stop()
        assert provider._is_running is False
    
    def test_rest_provider_get_snapshot_upbit(self):
        """REST 제공자: Upbit 호가 조회"""
        # Mock 호가 스냅샷
        mock_snapshot = OrderBookSnapshot(
            symbol="KRW-BTC",
            timestamp=1234567890.0,
            bids=[(50000000, 1.0)],
            asks=[(50100000, 1.0)],
        )
        
        # Mock 거래소
        mock_upbit = Mock()
        mock_upbit.get_orderbook.return_value = mock_snapshot
        
        exchanges = {"a": mock_upbit, "b": Mock()}
        provider = RestMarketDataProvider(exchanges)
        
        snapshot = provider.get_latest_snapshot("KRW-BTC")
        
        assert snapshot == mock_snapshot
        mock_upbit.get_orderbook.assert_called_once_with("KRW-BTC")
    
    def test_rest_provider_get_snapshot_binance(self):
        """REST 제공자: Binance 호가 조회"""
        # Mock 호가 스냅샷
        mock_snapshot = OrderBookSnapshot(
            symbol="BTCUSDT",
            timestamp=1234567890.0,
            bids=[(50000.0, 1.0)],
            asks=[(50100.0, 1.0)],
        )
        
        # Mock 거래소
        mock_binance = Mock()
        mock_binance.get_orderbook.return_value = mock_snapshot
        
        exchanges = {"a": Mock(), "b": mock_binance}
        provider = RestMarketDataProvider(exchanges)
        
        snapshot = provider.get_latest_snapshot("BTCUSDT")
        
        assert snapshot == mock_snapshot
        mock_binance.get_orderbook.assert_called_once_with("BTCUSDT")
    
    def test_rest_provider_get_snapshot_unknown_symbol(self):
        """REST 제공자: 알 수 없는 심볼"""
        exchanges = {"a": Mock(), "b": Mock()}
        provider = RestMarketDataProvider(exchanges)
        
        snapshot = provider.get_latest_snapshot("UNKNOWN")
        
        assert snapshot is None
    
    def test_rest_provider_get_snapshot_error(self):
        """REST 제공자: 에러 처리"""
        # Mock 거래소 (에러 발생)
        mock_upbit = Mock()
        mock_upbit.get_orderbook.side_effect = Exception("API error")
        
        exchanges = {"a": mock_upbit, "b": Mock()}
        provider = RestMarketDataProvider(exchanges)
        
        snapshot = provider.get_latest_snapshot("KRW-BTC")
        
        # 에러 시 None 반환
        assert snapshot is None


class TestD49WebSocketMarketDataProvider:
    """D49 WebSocket Market Data Provider 테스트"""
    
    def test_ws_provider_initialization(self):
        """WebSocket 제공자 초기화"""
        ws_adapters = {
            "upbit": Mock(),
            "binance": Mock(),
        }
        
        provider = WebSocketMarketDataProvider(ws_adapters)
        
        assert provider.ws_adapters == ws_adapters
        assert provider._is_running is False
        assert provider.snapshot_upbit is None
        assert provider.snapshot_binance is None
    
    def test_ws_provider_start_stop(self):
        """WebSocket 제공자 시작/종료"""
        ws_adapters = {"upbit": Mock(), "binance": Mock()}
        provider = WebSocketMarketDataProvider(ws_adapters)
        
        provider.start()
        assert provider._is_running is True
        
        provider.stop()
        assert provider._is_running is False
    
    def test_ws_provider_get_snapshot_empty(self):
        """WebSocket 제공자: 스냅샷 없음"""
        ws_adapters = {"upbit": Mock(), "binance": Mock()}
        provider = WebSocketMarketDataProvider(ws_adapters)
        
        snapshot = provider.get_latest_snapshot("KRW-BTC")
        
        # 초기 상태: 스냅샷 없음
        assert snapshot is None
    
    def test_ws_provider_update_snapshot(self):
        """WebSocket 제공자: 스냅샷 업데이트"""
        ws_adapters = {"upbit": Mock(), "binance": Mock()}
        provider = WebSocketMarketDataProvider(ws_adapters)
        
        # 스냅샷 생성
        snapshot = OrderBookSnapshot(
            symbol="KRW-BTC",
            timestamp=1234567890.0,
            bids=[(50000000, 1.0)],
            asks=[(50100000, 1.0)],
        )
        
        # 스냅샷 업데이트 (D49.5 API)
        provider.on_upbit_snapshot(snapshot)
        
        # 조회
        retrieved = provider.get_latest_snapshot("KRW-BTC")
        assert retrieved == snapshot
    
    def test_ws_provider_multiple_symbols(self):
        """WebSocket 제공자: 여러 심볼"""
        ws_adapters = {"upbit": Mock(), "binance": Mock()}
        provider = WebSocketMarketDataProvider(ws_adapters)
        
        # 여러 스냅샷 추가
        upbit_snapshot = OrderBookSnapshot(
            symbol="KRW-BTC",
            timestamp=1234567890.0,
            bids=[(50000000, 1.0)],
            asks=[(50100000, 1.0)],
        )
        
        binance_snapshot = OrderBookSnapshot(
            symbol="BTCUSDT",
            timestamp=1234567890.0,
            bids=[(50000.0, 1.0)],
            asks=[(50100.0, 1.0)],
        )
        
        # D49.5 API 사용
        provider.on_upbit_snapshot(upbit_snapshot)
        provider.on_binance_snapshot(binance_snapshot)
        
        # 각각 조회
        assert provider.get_latest_snapshot("KRW-BTC") == upbit_snapshot
        assert provider.get_latest_snapshot("BTCUSDT") == binance_snapshot
    
    def test_ws_provider_snapshot_overwrite(self):
        """WebSocket 제공자: 스냅샷 덮어쓰기"""
        ws_adapters = {"upbit": Mock(), "binance": Mock()}
        provider = WebSocketMarketDataProvider(ws_adapters)
        
        # 첫 번째 스냅샷
        snapshot1 = OrderBookSnapshot(
            symbol="KRW-BTC",
            timestamp=1000.0,
            bids=[(50000000, 1.0)],
            asks=[(50100000, 1.0)],
        )
        provider.on_upbit_snapshot(snapshot1)
        
        # 두 번째 스냅샷 (덮어쓰기)
        snapshot2 = OrderBookSnapshot(
            symbol="KRW-BTC",
            timestamp=2000.0,
            bids=[(50000000, 2.0)],
            asks=[(50100000, 2.0)],
        )
        provider.on_upbit_snapshot(snapshot2)
        
        # 최신 스냅샷 조회
        retrieved = provider.get_latest_snapshot("KRW-BTC")
        assert retrieved == snapshot2
        assert retrieved.timestamp == 2000.0


class TestD49MarketDataProviderComparison:
    """D49 Market Data Provider 비교 테스트"""
    
    def test_rest_vs_ws_interface(self):
        """REST vs WebSocket 인터페이스 동일성"""
        # 두 제공자 모두 동일한 인터페이스를 제공해야 함
        
        rest_provider = RestMarketDataProvider({"a": Mock(), "b": Mock()})
        ws_provider = WebSocketMarketDataProvider({"upbit": Mock(), "binance": Mock()})
        
        # 공통 메서드 확인
        assert hasattr(rest_provider, "get_latest_snapshot")
        assert hasattr(rest_provider, "start")
        assert hasattr(rest_provider, "stop")
        
        assert hasattr(ws_provider, "get_latest_snapshot")
        assert hasattr(ws_provider, "start")
        assert hasattr(ws_provider, "stop")
    
    def test_rest_provider_symbol_detection(self):
        """REST 제공자: 심볼 감지"""
        exchanges = {"a": Mock(), "b": Mock()}
        provider = RestMarketDataProvider(exchanges)
        
        # KRW-BTC 형식 (Upbit)
        exchange_a = provider._get_exchange_for_symbol("KRW-BTC")
        assert exchange_a == exchanges["a"]
        
        # BTCUSDT 형식 (Binance)
        exchange_b = provider._get_exchange_for_symbol("BTCUSDT")
        assert exchange_b == exchanges["b"]
        
        # 알 수 없는 형식
        exchange_none = provider._get_exchange_for_symbol("UNKNOWN")
        assert exchange_none is None
