"""
D49.5: WebSocket MarketDataProvider 통합 테스트

WebSocketMarketDataProvider와 WS 어댑터 통합을 검증한다.
"""

import pytest
from unittest.mock import Mock

from arbitrage.exchanges.base import OrderBookSnapshot
from arbitrage.exchanges.market_data_provider import WebSocketMarketDataProvider


class TestD495WebSocketMarketDataProvider:
    """D49.5 WebSocket MarketDataProvider 테스트"""
    
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
    
    def test_ws_provider_upbit_snapshot_callback(self):
        """Upbit 스냅샷 콜백"""
        ws_adapters = {"upbit": Mock(), "binance": Mock()}
        provider = WebSocketMarketDataProvider(ws_adapters)
        
        snapshot = OrderBookSnapshot(
            symbol="KRW-BTC",
            timestamp=1710000000.0,
            bids=[(50000000.0, 1.0)],
            asks=[(50100000.0, 1.0)],
        )
        
        provider.on_upbit_snapshot(snapshot)
        
        assert provider.snapshot_upbit == snapshot
    
    def test_ws_provider_binance_snapshot_callback(self):
        """Binance 스냅샷 콜백"""
        ws_adapters = {"upbit": Mock(), "binance": Mock()}
        provider = WebSocketMarketDataProvider(ws_adapters)
        
        snapshot = OrderBookSnapshot(
            symbol="BTCUSDT",
            timestamp=1710000000.0,
            bids=[(50000.0, 1.0)],
            asks=[(50001.0, 1.0)],
        )
        
        provider.on_binance_snapshot(snapshot)
        
        assert provider.snapshot_binance == snapshot
    
    def test_ws_provider_get_snapshot_upbit(self):
        """Upbit 스냅샷 조회"""
        ws_adapters = {"upbit": Mock(), "binance": Mock()}
        provider = WebSocketMarketDataProvider(ws_adapters)
        
        snapshot = OrderBookSnapshot(
            symbol="KRW-BTC",
            timestamp=1710000000.0,
            bids=[(50000000.0, 1.0)],
            asks=[(50100000.0, 1.0)],
        )
        
        provider.on_upbit_snapshot(snapshot)
        
        # 조회
        retrieved = provider.get_latest_snapshot("KRW-BTC")
        assert retrieved == snapshot
    
    def test_ws_provider_get_snapshot_binance(self):
        """Binance 스냅샷 조회"""
        ws_adapters = {"upbit": Mock(), "binance": Mock()}
        provider = WebSocketMarketDataProvider(ws_adapters)
        
        snapshot = OrderBookSnapshot(
            symbol="BTCUSDT",
            timestamp=1710000000.0,
            bids=[(50000.0, 1.0)],
            asks=[(50001.0, 1.0)],
        )
        
        provider.on_binance_snapshot(snapshot)
        
        # 조회
        retrieved = provider.get_latest_snapshot("BTCUSDT")
        assert retrieved == snapshot
    
    def test_ws_provider_get_snapshot_unknown_symbol(self):
        """알 수 없는 심볼 조회"""
        ws_adapters = {"upbit": Mock(), "binance": Mock()}
        provider = WebSocketMarketDataProvider(ws_adapters)
        
        retrieved = provider.get_latest_snapshot("UNKNOWN")
        assert retrieved is None
    
    def test_ws_provider_snapshot_overwrite(self):
        """스냅샷 덮어쓰기"""
        ws_adapters = {"upbit": Mock(), "binance": Mock()}
        provider = WebSocketMarketDataProvider(ws_adapters)
        
        # 첫 번째 스냅샷
        snapshot1 = OrderBookSnapshot(
            symbol="KRW-BTC",
            timestamp=1000.0,
            bids=[(50000000.0, 1.0)],
            asks=[(50100000.0, 1.0)],
        )
        provider.on_upbit_snapshot(snapshot1)
        
        # 두 번째 스냅샷 (덮어쓰기)
        snapshot2 = OrderBookSnapshot(
            symbol="KRW-BTC",
            timestamp=2000.0,
            bids=[(50000000.0, 2.0)],
            asks=[(50100000.0, 2.0)],
        )
        provider.on_upbit_snapshot(snapshot2)
        
        # 최신 스냅샷 조회
        retrieved = provider.get_latest_snapshot("KRW-BTC")
        assert retrieved == snapshot2
        assert retrieved.timestamp == 2000.0


class TestD495WebSocketMarketDataProviderIntegration:
    """D49.5 WebSocket MarketDataProvider 통합 테스트"""
    
    def test_ws_provider_multiple_exchanges(self):
        """여러 거래소 동시 관리"""
        ws_adapters = {"upbit": Mock(), "binance": Mock()}
        provider = WebSocketMarketDataProvider(ws_adapters)
        
        # Upbit 스냅샷
        upbit_snapshot = OrderBookSnapshot(
            symbol="KRW-BTC",
            timestamp=1710000000.0,
            bids=[(50000000.0, 1.0)],
            asks=[(50100000.0, 1.0)],
        )
        
        # Binance 스냅샷
        binance_snapshot = OrderBookSnapshot(
            symbol="BTCUSDT",
            timestamp=1710000000.0,
            bids=[(50000.0, 1.0)],
            asks=[(50001.0, 1.0)],
        )
        
        provider.on_upbit_snapshot(upbit_snapshot)
        provider.on_binance_snapshot(binance_snapshot)
        
        # 각각 조회
        assert provider.get_latest_snapshot("KRW-BTC") == upbit_snapshot
        assert provider.get_latest_snapshot("BTCUSDT") == binance_snapshot
    
    def test_ws_provider_symbol_pattern_detection(self):
        """심볼 패턴 감지"""
        ws_adapters = {"upbit": Mock(), "binance": Mock()}
        provider = WebSocketMarketDataProvider(ws_adapters)
        
        # Upbit 스냅샷
        upbit_snapshot = OrderBookSnapshot(
            symbol="KRW-ETH",
            timestamp=1710000000.0,
            bids=[(3000000.0, 1.0)],
            asks=[(3010000.0, 1.0)],
        )
        provider.on_upbit_snapshot(upbit_snapshot)
        
        # Binance 스냅샷
        binance_snapshot = OrderBookSnapshot(
            symbol="ETHUSDT",
            timestamp=1710000000.0,
            bids=[(3000.0, 1.0)],
            asks=[(3001.0, 1.0)],
        )
        provider.on_binance_snapshot(binance_snapshot)
        
        # 심볼 패턴으로 조회
        assert provider.get_latest_snapshot("KRW-ETH") == upbit_snapshot  # "-" 패턴
        assert provider.get_latest_snapshot("ETHUSDT") == binance_snapshot  # "USDT" 패턴
    
    def test_ws_provider_empty_state(self):
        """초기 상태 (스냅샷 없음)"""
        ws_adapters = {"upbit": Mock(), "binance": Mock()}
        provider = WebSocketMarketDataProvider(ws_adapters)
        
        # 초기 상태: 스냅샷 없음
        assert provider.get_latest_snapshot("KRW-BTC") is None
        assert provider.get_latest_snapshot("BTCUSDT") is None
