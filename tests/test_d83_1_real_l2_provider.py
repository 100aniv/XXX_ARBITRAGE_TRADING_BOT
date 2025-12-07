"""
D83-1: Real L2 WebSocket Provider 테스트

UpbitL2WebSocketProvider의 기본 동작을 검증한다.
실제 네트워크 연결은 Mock/Fake WebSocketAdapter를 사용하여 테스트한다.
"""

import asyncio
import logging
import time
from typing import List, Dict, Any, Optional
from unittest.mock import Mock, MagicMock, patch

import pytest

from arbitrage.exchanges.base import OrderBookSnapshot
from arbitrage.exchanges.upbit_l2_ws_provider import UpbitL2WebSocketProvider
from arbitrage.exchanges.upbit_ws_adapter import UpbitWebSocketAdapter

logger = logging.getLogger(__name__)


class FakeWebSocketAdapter:
    """
    테스트용 Fake WebSocket Adapter
    
    실제 WebSocket 연결 없이 콜백을 통해 스냅샷을 주입할 수 있다.
    """
    
    def __init__(self, symbols: List[str], callback, **kwargs):
        """초기화"""
        self.symbols = symbols
        self.callback = callback
        self.is_connected = False
        self.messages = []  # 주입할 메시지 큐
    
    async def connect(self) -> None:
        """연결 (Fake)"""
        self.is_connected = True
        logger.debug("[FAKE_WS] Connected")
    
    async def disconnect(self) -> None:
        """연결 종료 (Fake)"""
        self.is_connected = False
        logger.debug("[FAKE_WS] Disconnected")
    
    async def subscribe(self, channels: List[str]) -> None:
        """구독 (Fake)"""
        logger.debug(f"[FAKE_WS] Subscribed to {channels}")
    
    def inject_snapshot(self, snapshot: OrderBookSnapshot) -> None:
        """
        테스트용: 스냅샷 주입
        
        Args:
            snapshot: 주입할 OrderBookSnapshot
        """
        self.callback(snapshot)


class TestUpbitL2WebSocketProvider:
    """UpbitL2WebSocketProvider 테스트"""
    
    def test_init(self):
        """초기화 테스트"""
        # Given
        symbols = ["KRW-BTC"]
        
        # When
        provider = UpbitL2WebSocketProvider(
            symbols=symbols,
            heartbeat_interval=30.0,
            timeout=10.0,
            max_reconnect_attempts=3,
            reconnect_backoff=2.0,
        )
        
        # Then
        assert provider.symbols == symbols
        assert provider.max_reconnect_attempts == 3
        assert provider.reconnect_backoff == 2.0
        assert len(provider.latest_snapshots) == 0
        assert not provider._is_running
    
    def test_snapshot_update_via_callback(self):
        """콜백을 통한 스냅샷 업데이트 테스트"""
        # Given
        symbols = ["KRW-BTC"]
        
        # Provider 먼저 생성 (adapter는 나중에 주입)
        provider = UpbitL2WebSocketProvider(
            symbols=symbols,
            ws_adapter=None,  # 일단 None
        )
        
        # FakeAdapter 생성 시 Provider의 _on_snapshot을 callback으로 전달
        fake_adapter = FakeWebSocketAdapter(
            symbols=symbols,
            callback=provider._on_snapshot
        )
        provider.ws_adapter = fake_adapter  # adapter 주입
        
        # When
        snapshot = OrderBookSnapshot(
            symbol="KRW-BTC",
            timestamp=time.time(),
            bids=[(50000.0, 0.5), (49900.0, 1.0)],
            asks=[(50100.0, 0.3), (50200.0, 0.8)],
        )
        fake_adapter.inject_snapshot(snapshot)
        
        # Then
        assert "KRW-BTC" in provider.latest_snapshots
        assert provider.latest_snapshots["KRW-BTC"] == snapshot
    
    def test_get_latest_snapshot(self):
        """get_latest_snapshot() 메서드 테스트"""
        # Given
        symbols = ["KRW-BTC"]
        
        provider = UpbitL2WebSocketProvider(
            symbols=symbols,
            ws_adapter=None,
        )
        
        fake_adapter = FakeWebSocketAdapter(
            symbols=symbols,
            callback=provider._on_snapshot
        )
        provider.ws_adapter = fake_adapter
        
        snapshot = OrderBookSnapshot(
            symbol="KRW-BTC",
            timestamp=time.time(),
            bids=[(50000.0, 0.5)],
            asks=[(50100.0, 0.3)],
        )
        fake_adapter.inject_snapshot(snapshot)
        
        # When
        result = provider.get_latest_snapshot("KRW-BTC")
        
        # Then
        assert result is not None
        assert result.symbol == "KRW-BTC"
        assert len(result.bids) == 1
        assert len(result.asks) == 1
    
    def test_get_latest_snapshot_no_data(self):
        """데이터 없을 때 get_latest_snapshot() 테스트"""
        # Given
        symbols = ["KRW-BTC"]
        fake_adapter = FakeWebSocketAdapter(symbols=symbols, callback=lambda s: None)
        
        provider = UpbitL2WebSocketProvider(
            symbols=symbols,
            ws_adapter=fake_adapter,
        )
        
        # When
        result = provider.get_latest_snapshot("KRW-ETH")  # 존재하지 않는 심볼
        
        # Then
        assert result is None
    
    def test_multiple_snapshots(self):
        """여러 스냅샷 업데이트 테스트"""
        # Given
        symbols = ["KRW-BTC", "KRW-ETH"]
        
        provider = UpbitL2WebSocketProvider(
            symbols=symbols,
            ws_adapter=None,
        )
        
        fake_adapter = FakeWebSocketAdapter(
            symbols=symbols,
            callback=provider._on_snapshot
        )
        provider.ws_adapter = fake_adapter
        
        # When
        snapshot1 = OrderBookSnapshot(
            symbol="KRW-BTC",
            timestamp=time.time(),
            bids=[(50000.0, 0.5)],
            asks=[(50100.0, 0.3)],
        )
        snapshot2 = OrderBookSnapshot(
            symbol="KRW-ETH",
            timestamp=time.time(),
            bids=[(3000.0, 10.0)],
            asks=[(3010.0, 8.0)],
        )
        fake_adapter.inject_snapshot(snapshot1)
        fake_adapter.inject_snapshot(snapshot2)
        
        # Then
        # D83-1.5: 심볼 매핑 추가로 4개 항목 (Upbit 형식 + 표준 심볼)
        assert len(provider.latest_snapshots) == 4
        assert "KRW-BTC" in provider.latest_snapshots
        assert "KRW-ETH" in provider.latest_snapshots
        assert "BTC" in provider.latest_snapshots  # 표준 심볼
        assert "ETH" in provider.latest_snapshots  # 표준 심볼
        assert provider.latest_snapshots["KRW-BTC"] == snapshot1
        assert provider.latest_snapshots["KRW-ETH"] == snapshot2
        assert provider.latest_snapshots["BTC"] == snapshot1  # 매핑 확인
        assert provider.latest_snapshots["ETH"] == snapshot2  # 매핑 확인
    
    def test_snapshot_overwrite(self):
        """스냅샷 덮어쓰기 테스트"""
        # Given
        symbols = ["KRW-BTC"]
        
        provider = UpbitL2WebSocketProvider(
            symbols=symbols,
            ws_adapter=None,
        )
        
        fake_adapter = FakeWebSocketAdapter(
            symbols=symbols,
            callback=provider._on_snapshot
        )
        provider.ws_adapter = fake_adapter
        
        # When
        snapshot1 = OrderBookSnapshot(
            symbol="KRW-BTC",
            timestamp=time.time(),
            bids=[(50000.0, 0.5)],
            asks=[(50100.0, 0.3)],
        )
        snapshot2 = OrderBookSnapshot(
            symbol="KRW-BTC",
            timestamp=time.time() + 1,
            bids=[(50010.0, 0.6)],  # 업데이트된 값
            asks=[(50110.0, 0.4)],
        )
        fake_adapter.inject_snapshot(snapshot1)
        fake_adapter.inject_snapshot(snapshot2)
        
        # Then
        assert provider.get_latest_snapshot("KRW-BTC") == snapshot2  # 최신 스냅샷
        assert provider.get_latest_snapshot("KRW-BTC").bids[0][0] == 50010.0
    
    def test_get_connection_status(self):
        """연결 상태 정보 테스트"""
        # Given
        symbols = ["KRW-BTC"]
        fake_adapter = FakeWebSocketAdapter(symbols=symbols, callback=lambda s: None)
        
        provider = UpbitL2WebSocketProvider(
            symbols=symbols,
            ws_adapter=fake_adapter,
        )
        
        # When
        status = provider.get_connection_status()
        
        # Then
        assert status["is_running"] is False
        assert status["reconnect_count"] == 0
        assert status["symbols"] == ["KRW-BTC"]
        assert status["snapshots_count"] == 0
        assert status["thread_alive"] is False


class TestUpbitL2WebSocketProviderIntegration:
    """
    UpbitL2WebSocketProvider 통합 테스트
    
    실제 WebSocket 연결 없이 초기화/종료만 검증한다.
    """
    
    @pytest.mark.skip(reason="실제 WebSocket 연결 필요 (테스트 환경에서는 skip)")
    def test_real_connection_init(self):
        """
        실제 연결 초기화 테스트 (Skip)
        
        실제 Upbit WebSocket에 연결하려면 네트워크가 필요하므로 skip.
        로컬에서 수동으로 실행하여 검증할 수 있다.
        """
        # Given
        symbols = ["KRW-BTC"]
        
        # When
        provider = UpbitL2WebSocketProvider(symbols=symbols)
        provider.start()
        
        # 연결 대기
        time.sleep(5)
        
        # Then
        status = provider.get_connection_status()
        assert status["is_running"] is True
        assert status["thread_alive"] is True
        
        # Cleanup
        provider.stop()
