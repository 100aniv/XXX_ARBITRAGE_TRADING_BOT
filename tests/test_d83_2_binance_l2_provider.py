# -*- coding: utf-8 -*-
"""
D83-2: BinanceL2WebSocketProvider 유닛 테스트

테스트 범위:
- FakeBinanceWebSocketAdapter 기반 테스트
- 스냅샷 콜백 업데이트
- 심볼 매핑 (BTCUSDT ↔ BTC)
- 최신 스냅샷 반환
- 연결 상태 관리
"""

import asyncio
import pytest
import time
from typing import Optional

from arbitrage.exchanges.base import OrderBookSnapshot
from arbitrage.exchanges.binance_l2_ws_provider import BinanceL2WebSocketProvider


class FakeBinanceWebSocketAdapter:
    """
    테스트용 Fake Binance WebSocket Adapter
    
    실제 WebSocket 연결 없이 스냅샷을 주입할 수 있도록 설계.
    """
    
    def __init__(self, symbols, callback, **kwargs):
        """
        Args:
            symbols: 구독할 심볼 목록
            callback: 스냅샷 업데이트 콜백
            **kwargs: 기타 파라미터 (무시)
        """
        self.symbols = symbols
        self.callback = callback
        self.is_connected = False
    
    async def connect(self):
        """연결 (no-op)"""
        self.is_connected = True
        await asyncio.sleep(0.01)  # prevent busy-wait
    
    async def subscribe(self, channels):
        """구독 (no-op)"""
        await asyncio.sleep(0.01)  # prevent busy-wait
    
    async def receive_loop(self):
        """메시지 수신 루프 (no-op)"""
        await asyncio.sleep(0.1)  # prevent busy-wait
    
    async def disconnect(self):
        """연결 종료 (no-op)"""
        self.is_connected = False
        await asyncio.sleep(0.01)
    
    def inject_snapshot(self, snapshot: OrderBookSnapshot):
        """테스트용 스냅샷 주입"""
        self.callback(snapshot)


class TestBinanceL2WebSocketProvider:
    """BinanceL2WebSocketProvider 유닛 테스트"""
    
    def test_init(self):
        """
        초기화 테스트
        
        Provider가 예외 없이 생성되는지 확인.
        """
        adapter = FakeBinanceWebSocketAdapter(
            symbols=["BTCUSDT"],
            callback=lambda x: None,
        )
        provider = BinanceL2WebSocketProvider(
            symbols=["BTCUSDT"],
            ws_adapter=adapter,
        )
        
        assert provider is not None
        assert provider.symbols == ["BTCUSDT"]
        assert len(provider.latest_snapshots) == 0
    
    def test_snapshot_update_via_callback(self):
        """
        콜백을 통한 스냅샷 업데이트 테스트
        
        Adapter가 콜백을 호출하면 latest_snapshots가 갱신되는지 확인.
        """
        provider = BinanceL2WebSocketProvider(
            symbols=["BTCUSDT"],
        )
        
        # Adapter 생성 후 callback 재설정
        adapter = FakeBinanceWebSocketAdapter(
            symbols=["BTCUSDT"],
            callback=provider._on_snapshot,
        )
        provider.ws_adapter = adapter
        
        # 스냅샷 주입
        snapshot = OrderBookSnapshot(
            symbol="BTCUSDT",
            timestamp=time.time(),
            bids=[(50000.0, 1.5)],
            asks=[(50001.0, 1.2)],
        )
        adapter.inject_snapshot(snapshot)
        
        # 최신 스냅샷 확인 (Binance 심볼)
        latest = provider.get_latest_snapshot("BTCUSDT")
        assert latest is not None
        assert latest.symbol == "BTCUSDT"
        assert latest.bids == [(50000.0, 1.5)]
        assert latest.asks == [(50001.0, 1.2)]
    
    def test_get_latest_snapshot(self):
        """
        표준 심볼로 최신 스냅샷 조회 테스트
        
        BTC로 요청했을 때 BTCUSDT 스냅샷이 반환되는지 확인.
        """
        provider = BinanceL2WebSocketProvider(
            symbols=["BTCUSDT"],
        )
        
        adapter = FakeBinanceWebSocketAdapter(
            symbols=["BTCUSDT"],
            callback=provider._on_snapshot,
        )
        provider.ws_adapter = adapter
        
        # 스냅샷 주입
        snapshot = OrderBookSnapshot(
            symbol="BTCUSDT",
            timestamp=time.time(),
            bids=[(50000.0, 1.5)],
            asks=[(50001.0, 1.2)],
        )
        adapter.inject_snapshot(snapshot)
        
        # 표준 심볼로 조회
        latest_btc = provider.get_latest_snapshot("BTC")
        assert latest_btc is not None
        assert latest_btc.symbol == "BTCUSDT"
        assert latest_btc.bids == [(50000.0, 1.5)]
    
    def test_get_latest_snapshot_no_data(self):
        """
        데이터 없을 때 None 반환 테스트
        """
        adapter = FakeBinanceWebSocketAdapter(
            symbols=["BTCUSDT"],
            callback=lambda x: None,
        )
        provider = BinanceL2WebSocketProvider(
            symbols=["BTCUSDT"],
            ws_adapter=adapter,
        )
        
        # 스냅샷 주입 없이 조회
        latest = provider.get_latest_snapshot("BTCUSDT")
        assert latest is None
        
        latest_btc = provider.get_latest_snapshot("BTC")
        assert latest_btc is None
    
    def test_multiple_snapshots_symbol_mapping(self):
        """
        심볼 매핑 테스트 (BTCUSDT ↔ BTC)
        
        BTCUSDT 스냅샷을 주입하면 BTC로도 조회 가능한지 확인.
        """
        provider = BinanceL2WebSocketProvider(
            symbols=["BTCUSDT"],
        )
        
        adapter = FakeBinanceWebSocketAdapter(
            symbols=["BTCUSDT"],
            callback=provider._on_snapshot,
        )
        provider.ws_adapter = adapter
        
        # 스냅샷 주입
        snapshot1 = OrderBookSnapshot(
            symbol="BTCUSDT",
            timestamp=time.time(),
            bids=[(50000.0, 1.5)],
            asks=[(50001.0, 1.2)],
        )
        adapter.inject_snapshot(snapshot1)
        
        # 두 가지 심볼로 모두 조회 가능
        latest_binance = provider.get_latest_snapshot("BTCUSDT")
        latest_standard = provider.get_latest_snapshot("BTC")
        
        assert latest_binance is not None
        assert latest_standard is not None
        assert latest_binance.symbol == "BTCUSDT"
        assert latest_standard.symbol == "BTCUSDT"
        assert latest_binance is latest_standard  # 같은 객체
    
    def test_snapshot_overwrite(self):
        """
        스냅샷 덮어쓰기 테스트
        
        새 스냅샷이 기존 스냅샷을 덮어쓰는지 확인.
        """
        provider = BinanceL2WebSocketProvider(
            symbols=["BTCUSDT"],
        )
        
        adapter = FakeBinanceWebSocketAdapter(
            symbols=["BTCUSDT"],
            callback=provider._on_snapshot,
        )
        provider.ws_adapter = adapter
        
        # 첫 번째 스냅샷
        snapshot1 = OrderBookSnapshot(
            symbol="BTCUSDT",
            timestamp=time.time(),
            bids=[(50000.0, 1.5)],
            asks=[(50001.0, 1.2)],
        )
        adapter.inject_snapshot(snapshot1)
        
        # 두 번째 스냅샷 (덮어쓰기)
        snapshot2 = OrderBookSnapshot(
            symbol="BTCUSDT",
            timestamp=time.time(),
            bids=[(51000.0, 2.0)],
            asks=[(51001.0, 1.8)],
        )
        adapter.inject_snapshot(snapshot2)
        
        # 최신 스냅샷 확인
        latest = provider.get_latest_snapshot("BTCUSDT")
        assert latest is not None
        assert latest.bids == [(51000.0, 2.0)]
        assert latest.asks == [(51001.0, 1.8)]
    
    def test_get_connection_status(self):
        """
        연결 상태 조회 테스트 (선택적)
        
        현재 BinanceL2WebSocketProvider에 get_connection_status가 없으면 SKIP.
        """
        adapter = FakeBinanceWebSocketAdapter(
            symbols=["BTCUSDT"],
            callback=lambda x: None,
        )
        provider = BinanceL2WebSocketProvider(
            symbols=["BTCUSDT"],
            ws_adapter=adapter,
        )
        
        # Provider가 get_connection_status 메서드를 가지고 있으면 테스트
        if hasattr(provider, "get_connection_status"):
            status = provider.get_connection_status()
            assert isinstance(status, dict)
        else:
            pytest.xfail("get_connection_status not implemented")


# Real Connection 테스트 (선택적, 실제 네트워크 연결 필요)
@pytest.mark.live_api
class TestBinanceL2WebSocketProviderIntegration:
    """실제 Binance WebSocket 연결 테스트 (통합 테스트)"""
    
    def test_real_connection_init(self):
        """
        실제 Binance WebSocket 연결 테스트
        
        주의: 실제 네트워크 연결 필요, CI/CD에서는 SKIP.
        """
        provider = BinanceL2WebSocketProvider(
            symbols=["BTCUSDT"],
            heartbeat_interval=30.0,
            timeout=10.0,
        )
        
        provider.start()
        time.sleep(5)  # 연결 대기
        
        # 최신 스냅샷 확인
        snapshot = provider.get_latest_snapshot("BTCUSDT")
        assert snapshot is not None
        assert snapshot.symbol == "BTCUSDT"
        assert len(snapshot.bids) > 0
        assert len(snapshot.asks) > 0
        
        provider.stop()
