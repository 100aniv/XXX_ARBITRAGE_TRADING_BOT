"""
D49.5: Upbit WebSocket Adapter

Upbit WebSocket 스트림을 구독하고 orderbook 메시지를 파싱하여
OrderbookSnapshot으로 변환한다.

메시지 포맷:
{
  "type": "orderbook",
  "code": "KRW-BTC",
  "timestamp": 1710000000000,
  "orderbook_units": [
    {"ask_price": 100.1, "bid_price": 99.9, "ask_size": 1.2, "bid_size": 1.1},
    ...
  ]
}

D59: Multi-Symbol WebSocket Support
- 여러 심볼을 한 번에 구독 가능 (symbols 리스트)
- 심볼별 스냅샷 독립 관리 (_last_snapshots Dict)
- 콜백 기반 심볼별 업데이트
"""

import logging
from typing import List, Optional, Callable, Dict, Any

from arbitrage.exchanges.base import OrderBookSnapshot
from arbitrage.exchanges.ws_client import BaseWebSocketClient

logger = logging.getLogger(__name__)


class UpbitWebSocketAdapter(BaseWebSocketClient):
    """
    Upbit WebSocket 어댑터
    
    책임:
    - Upbit WebSocket 연결
    - orderbook 채널 구독
    - 메시지 파싱 → OrderbookSnapshot 변환
    - 콜백 기반 업데이트
    """
    
    def __init__(
        self,
        symbols: List[str],
        callback: Callable[[OrderBookSnapshot], None],
        heartbeat_interval: float = 30.0,
        timeout: float = 10.0,
    ):
        """
        Args:
            symbols: 구독할 심볼 목록 (예: ["KRW-BTC", "KRW-ETH"])
            callback: 스냅샷 업데이트 콜백
            heartbeat_interval: heartbeat 간격 (초)
            timeout: 연결 타임아웃 (초)
        """
        super().__init__(
            url="wss://api.upbit.com/websocket/v1",
            heartbeat_interval=heartbeat_interval,
            timeout=timeout,
        )
        self.symbols = symbols
        self.callback = callback
        self._last_snapshots: Dict[str, OrderBookSnapshot] = {}
    
    async def subscribe(self, channels: List[str]) -> None:
        """
        orderbook 채널 구독
        
        Args:
            channels: 구독할 심볼 목록
        
        Note:
            Upbit WebSocket API는 배열 형태로 메시지를 요구합니다:
            [{"ticket":"UUID"}, {"type":"orderbook","codes":["KRW-BTC"]}]
        """
        import uuid
        
        # D83-1.6 FIX: Upbit API 정식 포맷 (배열 + ticket)
        message = [
            {"ticket": str(uuid.uuid4())},
            {"type": "orderbook", "codes": channels}
        ]
        
        logger.debug(f"[D49.5_UPBIT_DEBUG] Subscription message: {message}")
        
        try:
            # send_message는 dict만 받으므로, 직접 JSON 전송
            import json
            message_str = json.dumps(message)
            await self.ws.send(message_str)
            logger.info(f"[D49.5_UPBIT] Subscribed to: {channels}")
            logger.debug(f"[D49.5_UPBIT_DEBUG] Subscription successful, waiting for orderbook messages...")
        except Exception as e:
            logger.error(f"[D49.5_UPBIT] Subscribe error: {e}")
            raise
    
    def on_message(self, message: Dict[str, Any]) -> None:
        """
        메시지 핸들러
        
        Args:
            message: 수신한 메시지 (JSON 파싱됨)
        """
        try:
            msg_type = message.get("type")
            logger.debug(f"[D49.5_UPBIT_DEBUG] on_message called: type={msg_type}")
            
            if msg_type == "orderbook":
                snapshot = self._parse_message(message)
                if snapshot:
                    logger.debug(f"[D49.5_UPBIT_DEBUG] Snapshot parsed successfully: {snapshot.symbol}")
                    self._last_snapshots[snapshot.symbol] = snapshot
                    self.callback(snapshot)
            else:
                logger.debug(f"[D49.5_UPBIT_DEBUG] Ignoring non-orderbook message: type={msg_type}")
        except Exception as e:
            logger.error(f"[D49.5_UPBIT] Message handling error: {e}")
            self.on_error(e)
    
    def _parse_message(self, message: Dict[str, Any]) -> Optional[OrderBookSnapshot]:
        """
        Upbit 메시지 → OrderbookSnapshot 변환
        
        Args:
            message: Upbit 메시지
        
        Returns:
            OrderbookSnapshot 또는 None (파싱 실패)
        """
        try:
            code = message.get("code")
            timestamp = message.get("timestamp", 0)
            units = message.get("orderbook_units", [])
            
            if not code or not units:
                logger.warning("[D49.5_UPBIT] Missing code or units")
                return None
            
            bids = []
            asks = []
            
            # 상위 10개 호가 추출
            for unit in units[:10]:
                bid_price = unit.get("bid_price")
                bid_size = unit.get("bid_size")
                ask_price = unit.get("ask_price")
                ask_size = unit.get("ask_size")
                
                # bid 추가
                if bid_price is not None and bid_size is not None:
                    try:
                        bids.append((float(bid_price), float(bid_size)))
                    except (ValueError, TypeError) as e:
                        logger.warning(f"[D49.5_UPBIT] Invalid bid: {e}")
                
                # ask 추가
                if ask_price is not None and ask_size is not None:
                    try:
                        asks.append((float(ask_price), float(ask_size)))
                    except (ValueError, TypeError) as e:
                        logger.warning(f"[D49.5_UPBIT] Invalid ask: {e}")
            
            # 타임스탬프 정규화 (ms → s)
            timestamp_s = timestamp / 1000.0 if timestamp > 1e10 else timestamp
            
            snapshot = OrderBookSnapshot(
                symbol=code,
                timestamp=timestamp_s,
                bids=bids,
                asks=asks,
            )
            
            logger.debug(
                f"[D49.5_UPBIT] Parsed snapshot: {code}, "
                f"bids={len(bids)}, asks={len(asks)}, ts={timestamp_s}"
            )
            
            if bids and asks:
                logger.debug(
                    f"[D49.5_UPBIT_DEBUG] Top bid: {bids[0][0]:.2f} x {bids[0][1]:.4f}, "
                    f"Top ask: {asks[0][0]:.2f} x {asks[0][1]:.4f}"
                )
            
            return snapshot
        
        except Exception as e:
            logger.error(f"[D49.5_UPBIT] Parse error: {e}")
            return None
    
    def get_latest_snapshot(self, symbol: str) -> Optional[OrderBookSnapshot]:
        """
        최신 스냅샷 반환
        
        Args:
            symbol: 심볼 (예: "KRW-BTC")
        
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
        logger.error(f"[D49.5_UPBIT] Error: {error}")
    
    def on_reconnect(self) -> None:
        """
        재연결 핸들러
        """
        logger.info("[D49.5_UPBIT] Reconnected, re-subscribing...")
        # 재연결 후 채널 재구독 (실제 구현에서는 asyncio 필요)
