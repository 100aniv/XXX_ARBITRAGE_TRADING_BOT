"""
D49.5: Binance WebSocket Adapter

Binance WebSocket 스트림을 구독하고 depth 메시지를 파싱하여
OrderbookSnapshot으로 변환한다.

메시지 포맷:
{
  "stream": "btcusdt@depth20@100ms",
  "data": {
    "E": 1710000000000,
    "b": [["price","size"], ...],
    "a": [["price","size"], ...]
  }
}

D59: Multi-Symbol WebSocket Support
- 여러 심볼을 한 번에 구독 가능 (symbols 리스트)
- 심볼별 스냅샷 독립 관리 (_last_snapshots Dict)
- 콜백 기반 심볼별 업데이트
"""

import logging
import time
from typing import List, Optional, Callable, Dict, Any

from arbitrage.exchanges.base import OrderBookSnapshot
from arbitrage.exchanges.ws_client import BaseWebSocketClient

logger = logging.getLogger(__name__)


class BinanceWebSocketAdapter(BaseWebSocketClient):
    """
    Binance WebSocket 어댑터
    
    책임:
    - Binance WebSocket 연결
    - depth 채널 구독
    - 메시지 파싱 → OrderbookSnapshot 변환
    - 콜백 기반 업데이트
    """
    
    def __init__(
        self,
        symbols: List[str],
        callback: Callable[[OrderBookSnapshot], None],
        depth: str = "20",
        interval: str = "100ms",
        heartbeat_interval: float = 30.0,
        timeout: float = 10.0,
    ):
        """
        Args:
            symbols: 구독할 심볼 목록 (예: ["btcusdt", "ethusdt"])
            callback: 스냅샷 업데이트 콜백
            depth: 호가 깊이 (기본값: "20")
            interval: 업데이트 간격 (기본값: "100ms")
            heartbeat_interval: heartbeat 간격 (초)
            timeout: 연결 타임아웃 (초)
        """
        # D83-2: Binance Spot WebSocket (Upbit과 일관성)
        super().__init__(
            url="wss://stream.binance.com:9443/stream",
            heartbeat_interval=heartbeat_interval,
            timeout=timeout,
        )
        self.symbols = symbols
        self.callback = callback
        self.depth = depth
        self.interval = interval
        self._last_snapshots: Dict[str, OrderBookSnapshot] = {}
        self._request_id = 1
    
    async def subscribe(self, channels: List[str]) -> None:
        """
        depth 채널 구독
        
        Args:
            channels: 구독할 채널 목록 (예: ["btcusdt@depth20@100ms"])
        """
        message = {
            "method": "SUBSCRIBE",
            "params": channels,
            "id": self._request_id,
        }
        self._request_id += 1
        
        # D83-2 DEBUG: 구독 메시지 로깅
        logger.debug(f"[D83-2_BINANCE_DEBUG] Subscription message: {message}")
        
        try:
            await self.send_message(message)
            logger.info(f"[D49.5_BINANCE] Subscribed to: {channels}")
            logger.debug(f"[D83-2_BINANCE_DEBUG] Subscription successful, waiting for depth messages...")
        except Exception as e:
            logger.error(f"[D49.5_BINANCE] Subscribe error: {e}")
            raise
    
    def on_message(self, message: Dict[str, Any]) -> None:
        """
        메시지 핸들러
        
        Args:
            message: 수신한 메시지 (JSON 파싱됨)
        """
        try:
            # D83-2 DEBUG: 메시지 타입 로깅
            msg_stream = message.get("stream")
            data = message.get("data", {})
            
            # D83-2 FIX: Binance depth stream 메시지 구조
            # - Combined stream: {"stream": "...", "data": {...}}
            # - Data 내부: "lastUpdateId", "bids", "asks" (NOT "b", "a")
            logger.debug(f"[D83-2_BINANCE_DEBUG] on_message called: stream={msg_stream}, data_keys={list(data.keys())}")
            
            # depth 메시지 확인 (bids/asks 또는 b/a)
            has_bids_asks = ("bids" in data and "asks" in data) or ("b" in data and "a" in data)
            
            if has_bids_asks:
                snapshot = self._parse_message(message)
                if snapshot:
                    logger.debug(f"[D83-2_BINANCE_DEBUG] Snapshot parsed successfully: {snapshot.symbol}")
                    self._last_snapshots[snapshot.symbol] = snapshot
                    self.callback(snapshot)
            else:
                logger.debug(f"[D83-2_BINANCE_DEBUG] Ignoring non-depth message: stream={msg_stream}, data_keys={list(data.keys())}")
        except Exception as e:
            logger.error(f"[D49.5_BINANCE] Message handling error: {e}")
            self.on_error(e)
    
    def _parse_message(self, message: Dict[str, Any]) -> Optional[OrderBookSnapshot]:
        """
        Binance 메시지 → OrderbookSnapshot 변환
        
        Args:
            message: Binance 메시지
        
        Returns:
            OrderbookSnapshot 또는 None (파싱 실패)
        """
        try:
            stream = message.get("stream", "")
            data = message.get("data", {})
            
            if not stream or not data:
                logger.warning("[D49.5_BINANCE] Missing stream or data")
                return None
            
            # stream에서 symbol 추출
            # 예: "btcusdt@depth20@100ms" → "BTCUSDT"
            symbol = stream.split("@")[0].upper()
            
            # D83-2 FIX: Binance depth stream 필드명
            # - "bids" / "asks" (partial book depth)
            # - "b" / "a" (diff depth, depthUpdate)
            # - Timestamp: depth snapshot에는 "E" 없음, 현재 시각 사용
            timestamp_ms = data.get("E", data.get("e"))
            timestamp = timestamp_ms / 1000.0 if timestamp_ms else time.time()
            
            bids_raw = data.get("bids", data.get("b", []))
            asks_raw = data.get("asks", data.get("a", []))
            
            if not bids_raw or not asks_raw:
                logger.warning("[D49.5_BINANCE] Missing bids or asks")
                return None
            
            bids = []
            asks = []
            
            # bids 파싱 (상위 20개)
            for bid_pair in bids_raw[:20]:
                try:
                    if len(bid_pair) >= 2:
                        price = float(bid_pair[0])
                        size = float(bid_pair[1])
                        bids.append((price, size))
                except (ValueError, TypeError, IndexError) as e:
                    logger.warning(f"[D49.5_BINANCE] Invalid bid: {e}")
            
            # asks 파싱 (상위 20개)
            for ask_pair in asks_raw[:20]:
                try:
                    if len(ask_pair) >= 2:
                        price = float(ask_pair[0])
                        size = float(ask_pair[1])
                        asks.append((price, size))
                except (ValueError, TypeError, IndexError) as e:
                    logger.warning(f"[D49.5_BINANCE] Invalid ask: {e}")
            
            # 타임스탬프 정규화 (ms → s)
            timestamp_s = timestamp / 1000.0 if timestamp > 1e10 else timestamp
            
            snapshot = OrderBookSnapshot(
                symbol=symbol,
                timestamp=timestamp_s,
                bids=bids,
                asks=asks,
            )
            
            logger.debug(
                f"[D49.5_BINANCE] Parsed snapshot: {symbol}, "
                f"bids={len(bids)}, asks={len(asks)}, ts={timestamp_s}"
            )
            
            # D83-2 DEBUG: Top bid/ask 로깅
            if bids and asks:
                logger.debug(
                    f"[D83-2_BINANCE_DEBUG] Top bid: {bids[0][0]:.2f} x {bids[0][1]:.4f}, "
                    f"Top ask: {asks[0][0]:.2f} x {asks[0][1]:.4f}"
                )
            
            return snapshot
        
        except Exception as e:
            logger.error(f"[D49.5_BINANCE] Parse error: {e}")
            return None
    
    def get_latest_snapshot(self, symbol: str) -> Optional[OrderBookSnapshot]:
        """
        최신 스냅샷 반환
        
        Args:
            symbol: 심볼 (예: "BTCUSDT")
        
        Returns:
            OrderbookSnapshot 또는 None
        """
        return self._last_snapshots.get(symbol)
    
    def on_error(self, error: Exception) -> None:
        """
        에러 핸들러
        
        Args:
            error: 발생한 에러
        """
        logger.error(f"[D49.5_BINANCE] Error: {error}")
    
    def on_reconnect(self) -> None:
        """
        재연결 핸들러
        """
        logger.info("[D49.5_BINANCE] Reconnected, re-subscribing...")
        # 재연결 후 채널 재구독 (실제 구현에서는 asyncio 필요)
