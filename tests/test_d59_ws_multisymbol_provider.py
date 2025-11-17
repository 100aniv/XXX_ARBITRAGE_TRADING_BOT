# -*- coding: utf-8 -*-
"""
D59: WebSocket Multi-Symbol Data Pipeline (Phase 1) - Tests

WebSocketMarketDataProvider 멀티심볼 스냅샷 관리 및 symbol-aware 인터페이스 검증.
"""

import pytest
from arbitrage.exchanges.base import OrderBookSnapshot
from arbitrage.exchanges.market_data_provider import WebSocketMarketDataProvider


class TestWebSocketMarketDataProviderMultiSymbol:
    """WebSocketMarketDataProvider 멀티심볼 테스트"""
    
    def test_ws_provider_latest_snapshots_field(self):
        """WebSocketMarketDataProvider latest_snapshots 필드 확인"""
        provider = WebSocketMarketDataProvider(ws_adapters={})
        
        # D59 필드 확인
        assert hasattr(provider, 'latest_snapshots')
        assert isinstance(provider.latest_snapshots, dict)
        assert provider.latest_snapshots == {}
    
    def test_on_upbit_snapshot_stores_per_symbol(self):
        """Upbit 스냅샷 콜백이 심볼별로 저장"""
        provider = WebSocketMarketDataProvider(ws_adapters={})
        
        # 스냅샷 생성
        snapshot_btc = OrderBookSnapshot(
            symbol="KRW-BTC",
            timestamp=1000.0,
            bids=[(100.0, 1.0), (99.0, 2.0)],
            asks=[(101.0, 1.0), (102.0, 2.0)],
        )
        
        snapshot_eth = OrderBookSnapshot(
            symbol="KRW-ETH",
            timestamp=1000.0,
            bids=[(50.0, 1.0), (49.0, 2.0)],
            asks=[(51.0, 1.0), (52.0, 2.0)],
        )
        
        # 콜백 호출
        provider.on_upbit_snapshot(snapshot_btc)
        provider.on_upbit_snapshot(snapshot_eth)
        
        # 확인
        assert "KRW-BTC" in provider.latest_snapshots
        assert "KRW-ETH" in provider.latest_snapshots
        assert provider.latest_snapshots["KRW-BTC"] == snapshot_btc
        assert provider.latest_snapshots["KRW-ETH"] == snapshot_eth
    
    def test_on_binance_snapshot_stores_per_symbol(self):
        """Binance 스냅샷 콜백이 심볼별로 저장"""
        provider = WebSocketMarketDataProvider(ws_adapters={})
        
        # 스냅샷 생성
        snapshot_btc = OrderBookSnapshot(
            symbol="BTCUSDT",
            timestamp=1000.0,
            bids=[(50000.0, 0.1), (49999.0, 0.2)],
            asks=[(50001.0, 0.1), (50002.0, 0.2)],
        )
        
        snapshot_eth = OrderBookSnapshot(
            symbol="ETHUSDT",
            timestamp=1000.0,
            bids=[(3000.0, 1.0), (2999.0, 2.0)],
            asks=[(3001.0, 1.0), (3002.0, 2.0)],
        )
        
        # 콜백 호출
        provider.on_binance_snapshot(snapshot_btc)
        provider.on_binance_snapshot(snapshot_eth)
        
        # 확인
        assert "BTCUSDT" in provider.latest_snapshots
        assert "ETHUSDT" in provider.latest_snapshots
        assert provider.latest_snapshots["BTCUSDT"] == snapshot_btc
        assert provider.latest_snapshots["ETHUSDT"] == snapshot_eth
    
    def test_get_latest_snapshot_per_symbol(self):
        """get_latest_snapshot이 심볼별 스냅샷 반환"""
        provider = WebSocketMarketDataProvider(ws_adapters={})
        
        # 스냅샷 생성 및 저장
        snapshot_btc = OrderBookSnapshot(
            symbol="KRW-BTC",
            timestamp=1000.0,
            bids=[(100.0, 1.0)],
            asks=[(101.0, 1.0)],
        )
        
        snapshot_eth = OrderBookSnapshot(
            symbol="KRW-ETH",
            timestamp=1000.0,
            bids=[(50.0, 1.0)],
            asks=[(51.0, 1.0)],
        )
        
        provider.on_upbit_snapshot(snapshot_btc)
        provider.on_upbit_snapshot(snapshot_eth)
        
        # 확인
        assert provider.get_latest_snapshot("KRW-BTC") == snapshot_btc
        assert provider.get_latest_snapshot("KRW-ETH") == snapshot_eth
    
    def test_get_latest_snapshot_none_if_not_found(self):
        """get_latest_snapshot이 없는 심볼에 대해 None 반환"""
        provider = WebSocketMarketDataProvider(ws_adapters={})
        
        # 확인
        assert provider.get_latest_snapshot("KRW-BTC") is None
        assert provider.get_latest_snapshot("BTCUSDT") is None
    
    def test_mixed_upbit_binance_symbols(self):
        """Upbit과 Binance 심볼이 독립적으로 관리"""
        provider = WebSocketMarketDataProvider(ws_adapters={})
        
        # Upbit 스냅샷
        upbit_btc = OrderBookSnapshot(
            symbol="KRW-BTC",
            timestamp=1000.0,
            bids=[(100.0, 1.0)],
            asks=[(101.0, 1.0)],
        )
        
        # Binance 스냅샷
        binance_btc = OrderBookSnapshot(
            symbol="BTCUSDT",
            timestamp=1000.0,
            bids=[(50000.0, 0.1)],
            asks=[(50001.0, 0.1)],
        )
        
        # 저장
        provider.on_upbit_snapshot(upbit_btc)
        provider.on_binance_snapshot(binance_btc)
        
        # 확인: 각 심볼이 독립적으로 저장됨
        assert provider.get_latest_snapshot("KRW-BTC") == upbit_btc
        assert provider.get_latest_snapshot("BTCUSDT") == binance_btc
        assert provider.latest_snapshots["KRW-BTC"] != provider.latest_snapshots["BTCUSDT"]
    
    def test_snapshot_update_overwrites_previous(self):
        """같은 심볼의 스냅샷 업데이트가 이전 값을 덮어씀"""
        provider = WebSocketMarketDataProvider(ws_adapters={})
        
        # 첫 번째 스냅샷
        snapshot_v1 = OrderBookSnapshot(
            symbol="KRW-BTC",
            timestamp=1000.0,
            bids=[(100.0, 1.0)],
            asks=[(101.0, 1.0)],
        )
        
        # 두 번째 스냅샷 (같은 심볼)
        snapshot_v2 = OrderBookSnapshot(
            symbol="KRW-BTC",
            timestamp=2000.0,
            bids=[(100.5, 1.0)],
            asks=[(101.5, 1.0)],
        )
        
        # 저장
        provider.on_upbit_snapshot(snapshot_v1)
        assert provider.get_latest_snapshot("KRW-BTC") == snapshot_v1
        
        provider.on_upbit_snapshot(snapshot_v2)
        assert provider.get_latest_snapshot("KRW-BTC") == snapshot_v2
    
    def test_multiple_symbols_independent_tracking(self):
        """여러 심볼의 독립적인 추적"""
        provider = WebSocketMarketDataProvider(ws_adapters={})
        
        # 4개 심볼 스냅샷 생성
        symbols = ["KRW-BTC", "KRW-ETH", "BTCUSDT", "ETHUSDT"]
        snapshots = {}
        
        for i, symbol in enumerate(symbols):
            snapshot = OrderBookSnapshot(
                symbol=symbol,
                timestamp=1000.0 + i,
                bids=[(100.0 + i, 1.0)],
                asks=[(101.0 + i, 1.0)],
            )
            snapshots[symbol] = snapshot
        
        # Upbit 스냅샷 저장
        provider.on_upbit_snapshot(snapshots["KRW-BTC"])
        provider.on_upbit_snapshot(snapshots["KRW-ETH"])
        
        # Binance 스냅샷 저장
        provider.on_binance_snapshot(snapshots["BTCUSDT"])
        provider.on_binance_snapshot(snapshots["ETHUSDT"])
        
        # 각 심볼이 독립적으로 저장되었는지 확인
        for symbol in symbols:
            assert provider.get_latest_snapshot(symbol) == snapshots[symbol]
        
        # 전체 개수 확인
        assert len(provider.latest_snapshots) == 4


class TestWebSocketMarketDataProviderBackwardCompatibility:
    """D59 추가 후 기존 기능 호환성"""
    
    def test_snapshot_upbit_field_still_works(self):
        """기존 snapshot_upbit 필드 유지"""
        provider = WebSocketMarketDataProvider(ws_adapters={})
        
        snapshot = OrderBookSnapshot(
            symbol="KRW-BTC",
            timestamp=1000.0,
            bids=[(100.0, 1.0)],
            asks=[(101.0, 1.0)],
        )
        
        provider.on_upbit_snapshot(snapshot)
        
        # 기존 필드도 업데이트되어야 함
        assert provider.snapshot_upbit == snapshot
    
    def test_snapshot_binance_field_still_works(self):
        """기존 snapshot_binance 필드 유지"""
        provider = WebSocketMarketDataProvider(ws_adapters={})
        
        snapshot = OrderBookSnapshot(
            symbol="BTCUSDT",
            timestamp=1000.0,
            bids=[(50000.0, 0.1)],
            asks=[(50001.0, 0.1)],
        )
        
        provider.on_binance_snapshot(snapshot)
        
        # 기존 필드도 업데이트되어야 함
        assert provider.snapshot_binance == snapshot
