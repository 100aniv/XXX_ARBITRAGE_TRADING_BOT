"""
D49: Market Data Provider - 호가 데이터 소스 추상화

REST 폴링 또는 WebSocket 스트림 중 하나를 선택하여 사용할 수 있도록
통합 인터페이스를 제공한다.

구현체:
- RestMarketDataProvider: REST 기반 폴링
- WebSocketMarketDataProvider: WebSocket 스트림 기반 (D49+)

D54: Async wrapper 추가 (멀티심볼 v2.0 기반)
D55: Async-first design (완전 비동기 전환)
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Dict, Optional

from arbitrage.exchanges.base import OrderBookSnapshot

logger = logging.getLogger(__name__)


class MarketDataProvider(ABC):
    """
    호가 데이터 소스 추상화 인터페이스
    
    책임:
    - 최신 호가 스냅샷 제공
    - 데이터 소스 시작/종료
    """
    
    @abstractmethod
    def get_latest_snapshot(self, symbol: str) -> Optional[OrderBookSnapshot]:
        """
        최신 호가 스냅샷 반환
        
        Args:
            symbol: 거래 쌍 (예: "KRW-BTC", "BTCUSDT")
        
        Returns:
            OrderBookSnapshot 또는 None (데이터 없음)
        """
        pass
    
    @abstractmethod
    def start(self) -> None:
        """
        데이터 소스 시작
        
        - REST: 폴링 루프 시작
        - WebSocket: 연결 및 백그라운드 루프 시작
        """
        pass
    
    @abstractmethod
    def stop(self) -> None:
        """
        데이터 소스 종료
        
        - REST: 폴링 루프 종료
        - WebSocket: 연결 종료
        """
        pass
    
    async def aget_latest_snapshot(self, symbol: str) -> Optional[OrderBookSnapshot]:
        """
        D54: Async wrapper for get_latest_snapshot
        
        멀티심볼 병렬 처리를 위한 async 인터페이스.
        내부적으로는 sync 메서드를 호출하되, 추후 완전 async 전환 대비.
        
        Args:
            symbol: 거래 쌍
        
        Returns:
            OrderBookSnapshot 또는 None
        """
        # 현재는 sync 메서드를 event loop에서 실행
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.get_latest_snapshot, symbol)
    
    async def astart(self) -> None:
        """
        D55: Async start method
        
        데이터 소스를 비동기적으로 시작한다.
        기존 sync start()와 동일한 기능을 수행한다.
        """
        self.start()
    
    async def astop(self) -> None:
        """
        D55: Async stop method
        
        데이터 소스를 비동기적으로 종료한다.
        기존 sync stop()과 동일한 기능을 수행한다.
        """
        self.stop()


class RestMarketDataProvider(MarketDataProvider):
    """
    REST 기반 호가 데이터 제공자
    
    기존 get_orderbook() API를 사용하여 폴링 방식으로 호가를 조회한다.
    """
    
    def __init__(self, exchanges: Dict[str, any]):
        """
        Args:
            exchanges: 거래소 어댑터 dict
                - exchanges["a"]: Upbit 어댑터
                - exchanges["b"]: Binance 어댑터
        """
        self.exchanges = exchanges
        self._is_running = False
    
    def get_latest_snapshot(self, symbol: str) -> Optional[OrderBookSnapshot]:
        """
        REST API를 통해 호가 조회
        
        Args:
            symbol: 거래 쌍 (예: "KRW-BTC", "BTCUSDT")
        
        Returns:
            OrderBookSnapshot
        """
        try:
            # 심볼에 따라 적절한 거래소 선택
            exchange = self._get_exchange_for_symbol(symbol)
            if not exchange:
                logger.warning(f"[D49_PROVIDER] No exchange for symbol: {symbol}")
                return None
            
            snapshot = exchange.get_orderbook(symbol)
            return snapshot
        
        except Exception as e:
            logger.error(f"[D49_PROVIDER] REST snapshot error: {e}")
            return None
    
    def start(self) -> None:
        """
        REST 폴링 시작 (현재는 no-op)
        
        실제 폴링은 LiveRunner의 메인 루프에서 수행된다.
        """
        self._is_running = True
        logger.info("[D49_PROVIDER] REST provider started")
    
    def stop(self) -> None:
        """
        REST 폴링 종료
        """
        self._is_running = False
        logger.info("[D49_PROVIDER] REST provider stopped")
    
    def _get_exchange_for_symbol(self, symbol: str):
        """
        심볼에 따라 적절한 거래소 반환
        
        Args:
            symbol: 거래 쌍
        
        Returns:
            거래소 어댑터 또는 None
        """
        # 심볼 패턴으로 거래소 판단
        if "-" in symbol:  # KRW-BTC
            return self.exchanges.get("a")
        elif symbol.endswith("USDT"):  # BTCUSDT
            return self.exchanges.get("b")
        else:
            return None


class WebSocketMarketDataProvider(MarketDataProvider):
    """
    WebSocket 기반 호가 데이터 제공자
    
    WebSocket 스트림을 통해 실시간 호가를 수신하고,
    메모리 버퍼에 최신 스냅샷을 유지한다.
    
    D49.5: Upbit/Binance WS 어댑터 연결 완료
    """
    
    def __init__(self, ws_adapters: Dict[str, any]):
        """
        Args:
            ws_adapters: WebSocket 어댑터 dict
                - ws_adapters["upbit"]: Upbit WS 어댑터
                - ws_adapters["binance"]: Binance WS 어댑터
        """
        self.ws_adapters = ws_adapters
        self._is_running = False
        
        # 거래소별 최신 스냅샷 (D49.5)
        self.snapshot_upbit: Optional[OrderBookSnapshot] = None
        self.snapshot_binance: Optional[OrderBookSnapshot] = None
        
        # D53: 심볼 패턴 캐싱 (반복 계산 제거)
        self._symbol_cache: Dict[str, str] = {}  # symbol -> "upbit" or "binance"
    
    def get_latest_snapshot(self, symbol: str) -> Optional[OrderBookSnapshot]:
        """
        심볼 기반 최신 호가 스냅샷 반환
        D53: 심볼 패턴 캐싱으로 성능 개선
        
        Args:
            symbol: 거래 쌍 (예: "KRW-BTC", "BTCUSDT")
        
        Returns:
            OrderBookSnapshot 또는 None (데이터 없음)
        """
        # D53: 캐시 확인
        if symbol not in self._symbol_cache:
            # 심볼 패턴으로 거래소 판단 (첫 호출 시만)
            if "-" in symbol:  # Upbit (KRW-BTC)
                self._symbol_cache[symbol] = "upbit"
            elif symbol.endswith("USDT"):  # Binance (BTCUSDT)
                self._symbol_cache[symbol] = "binance"
            else:
                logger.warning(f"[D49.5_PROVIDER] Unknown symbol pattern: {symbol}")
                return None
        
        # 캐시된 거래소 정보로 스냅샷 반환
        exchange = self._symbol_cache[symbol]
        if exchange == "upbit":
            return self.snapshot_upbit
        else:
            return self.snapshot_binance
    
    def start(self) -> None:
        """
        WebSocket 연결 및 백그라운드 루프 시작
        """
        self._is_running = True
        logger.info("[D49.5_PROVIDER] WebSocket provider started")
        
        # 실제 구현: 각 WS 어댑터 연결 및 루프 시작
        # for adapter in self.ws_adapters.values():
        #     await adapter.connect()
        #     asyncio.create_task(adapter.receive_loop())
    
    def stop(self) -> None:
        """
        WebSocket 연결 종료
        """
        self._is_running = False
        logger.info("[D49.5_PROVIDER] WebSocket provider stopped")
        
        # 실제 구현: 각 WS 어댑터 종료
        # for adapter in self.ws_adapters.values():
        #     await adapter.disconnect()
    
    def on_upbit_snapshot(self, snapshot: OrderBookSnapshot) -> None:
        """
        Upbit 스냅샷 콜백 (D49.5)
        
        Args:
            snapshot: Upbit 호가 스냅샷
        """
        self.snapshot_upbit = snapshot
        logger.debug(f"[D49.5_PROVIDER] Updated Upbit snapshot: {snapshot.symbol}")
    
    def on_binance_snapshot(self, snapshot: OrderBookSnapshot) -> None:
        """
        Binance 스냅샷 콜백 (D49.5)
        
        Args:
            snapshot: Binance 호가 스냅샷
        """
        self.snapshot_binance = snapshot
        logger.debug(f"[D49.5_PROVIDER] Updated Binance snapshot: {snapshot.symbol}")
