"""
D83-1: Real L2 WebSocket Provider (Upbit)

Upbit Public WebSocket을 통해 실시간 L2 Orderbook을 제공하는 MarketDataProvider 구현.

특징:
- MarketDataProvider 인터페이스 완전 준수
- UpbitWebSocketAdapter 재사용
- 별도 스레드 + asyncio event loop (Executor 동기 호출 지원)
- 자동 재연결 (exponential backoff)
- 테스트 가능 설계 (adapter 주입)

Usage:
    provider = UpbitL2WebSocketProvider(symbols=["KRW-BTC"])
    provider.start()
    
    # ... Executor에서 사용
    snapshot = provider.get_latest_snapshot("KRW-BTC")
    
    provider.stop()
"""

import asyncio
import logging
import threading
import time
from typing import Dict, List, Optional

from arbitrage.exchanges.base import OrderBookSnapshot
from arbitrage.exchanges.market_data_provider import MarketDataProvider
from arbitrage.exchanges.upbit_ws_adapter import UpbitWebSocketAdapter

logger = logging.getLogger(__name__)


class UpbitL2WebSocketProvider(MarketDataProvider):
    """
    D83-1: Real L2 WebSocket Provider (Upbit)
    
    Upbit Public WebSocket을 통해 실시간 L2 Orderbook을 제공.
    
    책임:
    - MarketDataProvider 인터페이스 구현
    - WebSocket 연결 관리 (재연결 포함)
    - 최신 스냅샷 버퍼링
    - 스레드 안전성 보장
    """
    
    def __init__(
        self,
        symbols: List[str],
        ws_adapter: Optional[UpbitWebSocketAdapter] = None,
        heartbeat_interval: float = 30.0,
        timeout: float = 10.0,
        max_reconnect_attempts: int = 5,
        reconnect_backoff: float = 2.0,
    ):
        """
        Args:
            symbols: 구독할 심볼 목록 (예: ["KRW-BTC"])
            ws_adapter: WebSocket Adapter (테스트용 주입, None이면 자동 생성)
            heartbeat_interval: heartbeat 간격 (초)
            timeout: 연결 타임아웃 (초)
            max_reconnect_attempts: 최대 재연결 시도 횟수
            reconnect_backoff: 재연결 backoff 배수
        """
        self.symbols = symbols
        self.heartbeat_interval = heartbeat_interval
        self.timeout = timeout
        self.max_reconnect_attempts = max_reconnect_attempts
        self.reconnect_backoff = reconnect_backoff
        
        # 최신 스냅샷 버퍼 (심볼별)
        self.latest_snapshots: Dict[str, OrderBookSnapshot] = {}
        
        # 상태 관리
        self._is_running = False
        self._reconnect_count = 0
        self._thread: Optional[threading.Thread] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        
        # WebSocket Adapter (주입 or 생성)
        if ws_adapter:
            self.ws_adapter = ws_adapter
        else:
            self.ws_adapter = UpbitWebSocketAdapter(
                symbols=symbols,
                callback=self._on_snapshot,
                heartbeat_interval=heartbeat_interval,
                timeout=timeout,
            )
        
        logger.info(
            f"[D83-1_L2] UpbitL2WebSocketProvider initialized for {symbols}"
        )
    
    def start(self) -> None:
        """
        WebSocket 연결 및 백그라운드 루프 시작
        
        별도 스레드에서 asyncio event loop를 실행하여 WebSocket 연결을 유지한다.
        """
        if self._is_running:
            logger.warning("[D83-1_L2] Provider already running")
            return
        
        self._is_running = True
        self._reconnect_count = 0
        
        # 별도 스레드에서 asyncio loop 실행
        self._thread = threading.Thread(
            target=self._run_event_loop,
            daemon=True,
            name="UpbitL2WebSocketProvider"
        )
        self._thread.start()
        
        logger.info(f"[D83-1_L2] WebSocket provider started for {self.symbols}")
    
    def stop(self) -> None:
        """
        WebSocket 연결 종료
        """
        if not self._is_running:
            return
        
        logger.info("[D83-1_L2] Stopping WebSocket provider...")
        self._is_running = False
        
        # Event loop 종료 신호
        if self._loop and not self._loop.is_closed():
            # Disconnect 태스크 스케줄링
            future = asyncio.run_coroutine_threadsafe(
                self._stop_websocket(),
                self._loop
            )
            try:
                future.result(timeout=5.0)
            except Exception as e:
                logger.warning(f"[D83-1_L2] Stop error: {e}")
        
        # 스레드 종료 대기 (타임아웃)
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5.0)
            if self._thread.is_alive():
                logger.warning("[D83-1_L2] Thread did not stop gracefully")
        
        logger.info("[D83-1_L2] WebSocket provider stopped")
    
    def get_latest_snapshot(self, symbol: str) -> Optional[OrderBookSnapshot]:
        """
        최신 호가 스냅샷 반환
        
        Args:
            symbol: 거래 쌍 (예: "KRW-BTC")
        
        Returns:
            OrderBookSnapshot 또는 None (데이터 없음)
        """
        snapshot = self.latest_snapshots.get(symbol)
        
        if snapshot:
            # 스냅샷 age 체크 (5초 이상 오래된 데이터는 경고)
            age_ms = (time.time() - snapshot.timestamp) * 1000
            if age_ms > 5000:
                logger.warning(
                    f"[D83-1_L2] Stale snapshot for {symbol}: {age_ms:.0f}ms old"
                )
        
        return snapshot
    
    def _on_snapshot(self, snapshot: OrderBookSnapshot) -> None:
        """
        WebSocket Adapter 콜백: 스냅샷 업데이트
        
        Args:
            snapshot: Upbit 호가 스냅샷
        """
        self.latest_snapshots[snapshot.symbol] = snapshot
        
        logger.debug(
            f"[D83-1_L2] Updated snapshot: {snapshot.symbol}, "
            f"bids={len(snapshot.bids)}, asks={len(snapshot.asks)}, "
            f"timestamp={snapshot.timestamp:.3f}"
        )
    
    def _run_event_loop(self) -> None:
        """
        별도 스레드에서 asyncio event loop 실행
        
        WebSocket 연결 및 재연결 로직을 포함한 메인 루프.
        """
        # 새 event loop 생성
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        
        try:
            logger.info("[D83-1_L2] Starting event loop...")
            self._loop.run_until_complete(self._connect_and_subscribe())
        except Exception as e:
            logger.error(f"[D83-1_L2] Event loop error: {e}", exc_info=True)
        finally:
            try:
                self._loop.run_until_complete(self._loop.shutdown_asyncgens())
                self._loop.close()
            except Exception as e:
                logger.warning(f"[D83-1_L2] Loop cleanup error: {e}")
            
            logger.info("[D83-1_L2] Event loop stopped")
    
    async def _connect_and_subscribe(self) -> None:
        """
        WebSocket 연결 및 구독 (재연결 로직 포함)
        
        최대 `max_reconnect_attempts`까지 재연결을 시도하며,
        exponential backoff를 사용한다.
        """
        while self._is_running and self._reconnect_count < self.max_reconnect_attempts:
            try:
                logger.info(
                    f"[D83-1_L2] Connecting... (attempt {self._reconnect_count + 1})"
                )
                
                # WebSocket 연결
                await self.ws_adapter.connect()
                
                # 채널 구독
                await self.ws_adapter.subscribe(self.symbols)
                
                logger.info(f"[D83-1_L2] Connected and subscribed to {self.symbols}")
                
                # 재연결 카운터 리셋 (연결 성공)
                self._reconnect_count = 0
                
                # 연결 유지 (메시지 수신은 ws_adapter가 처리)
                while self._is_running:
                    await asyncio.sleep(1.0)
                
                # 정상 종료 요청
                break
            
            except asyncio.CancelledError:
                logger.info("[D83-1_L2] Connection cancelled")
                break
            
            except Exception as e:
                self._reconnect_count += 1
                
                if self._reconnect_count >= self.max_reconnect_attempts:
                    logger.error(
                        f"[D83-1_L2] Max reconnect attempts ({self.max_reconnect_attempts}) reached. "
                        "Giving up."
                    )
                    self._is_running = False
                    break
                
                # Exponential backoff 계산
                backoff_delay = min(
                    self.reconnect_backoff ** self._reconnect_count,
                    60.0  # 최대 60초
                )
                
                logger.error(
                    f"[D83-1_L2] Connection error (attempt {self._reconnect_count}/{self.max_reconnect_attempts}): {e}"
                )
                logger.info(f"[D83-1_L2] Reconnecting in {backoff_delay:.1f}s...")
                
                await asyncio.sleep(backoff_delay)
    
    async def _stop_websocket(self) -> None:
        """
        WebSocket 연결 종료 (내부 헬퍼)
        """
        try:
            if hasattr(self.ws_adapter, 'disconnect'):
                await self.ws_adapter.disconnect()
        except Exception as e:
            logger.warning(f"[D83-1_L2] Disconnect error: {e}")
    
    def get_connection_status(self) -> Dict[str, any]:
        """
        연결 상태 정보 반환 (디버깅/모니터링용)
        
        Returns:
            {is_running, reconnect_count, symbols_count, ...} dict
        """
        return {
            "is_running": self._is_running,
            "reconnect_count": self._reconnect_count,
            "symbols": self.symbols,
            "snapshots_count": len(self.latest_snapshots),
            "thread_alive": self._thread.is_alive() if self._thread else False,
        }
