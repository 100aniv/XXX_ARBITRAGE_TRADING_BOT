#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
D83-2: Binance WebSocket 독립 디버그 스크립트

목적:
- D83-1.6 Upbit WebSocket 디버깅 패턴 재사용
- Binance Spot WebSocket 연결 테스트
- 메시지 수신 및 파싱 검증
- BinanceL2WebSocketProvider 통합 전 독립 검증

실행:
    python scripts/debug/d83_2_binance_ws_debug.py
"""

import asyncio
import json
import logging
import sys
import time
from pathlib import Path
from typing import Dict, Any

# 프로젝트 루트 추가
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from arbitrage.exchanges.binance_ws_adapter import BinanceWebSocketAdapter
from arbitrage.exchanges.base import OrderBookSnapshot

logging.basicConfig(
    level=logging.DEBUG,
    format="[%(asctime)s] [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


class BinanceDebugStats:
    """디버그 통계"""
    
    def __init__(self):
        self.messages_received = 0
        self.orderbook_messages = 0
        self.other_messages = 0
        self.parse_success = 0
        self.parse_failures = 0
        self.first_message_time = None
        self.last_message_time = None
        self.snapshots = []
    
    def record_message(self, msg_type: str):
        """메시지 기록"""
        self.messages_received += 1
        
        if self.first_message_time is None:
            self.first_message_time = time.time()
        
        self.last_message_time = time.time()
        
        if msg_type == "orderbook":
            self.orderbook_messages += 1
        else:
            self.other_messages += 1
    
    def record_parse(self, success: bool, snapshot: OrderBookSnapshot = None):
        """파싱 결과 기록"""
        if success:
            self.parse_success += 1
            if snapshot:
                self.snapshots.append(snapshot)
        else:
            self.parse_failures += 1
    
    def print_summary(self):
        """통계 요약 출력"""
        logger.info("=" * 80)
        logger.info("[D83-2 DEBUG] Binance WebSocket 디버그 통계")
        logger.info("=" * 80)
        logger.info(f"총 메시지 수신: {self.messages_received}")
        logger.info(f"  - Orderbook 메시지: {self.orderbook_messages}")
        logger.info(f"  - 기타 메시지: {self.other_messages}")
        logger.info(f"파싱 성공: {self.parse_success}")
        logger.info(f"파싱 실패: {self.parse_failures}")
        
        if self.first_message_time and self.last_message_time:
            duration = self.last_message_time - self.first_message_time
            rate = self.messages_received / duration if duration > 0 else 0
            logger.info(f"실행 시간: {duration:.2f}초")
            logger.info(f"메시지 수신 속도: {rate:.2f} msg/s")
        
        if self.snapshots:
            latest = self.snapshots[-1]
            logger.info(f"\n최신 스냅샷:")
            logger.info(f"  - Symbol: {latest.symbol}")
            logger.info(f"  - Timestamp: {latest.timestamp:.3f}")
            logger.info(f"  - Bids: {len(latest.bids)}")
            logger.info(f"  - Asks: {len(latest.asks)}")
            if latest.bids and latest.asks:
                logger.info(f"  - Top Bid: {latest.bids[0][0]:.2f} x {latest.bids[0][1]:.8f}")
                logger.info(f"  - Top Ask: {latest.asks[0][0]:.2f} x {latest.asks[0][1]:.8f}")
        
        logger.info("=" * 80)


async def test_binance_websocket(duration_seconds: int = 30):
    """
    Binance WebSocket 독립 테스트
    
    Args:
        duration_seconds: 실행 시간 (초)
    """
    stats = BinanceDebugStats()
    
    def on_snapshot(snapshot: OrderBookSnapshot):
        """스냅샷 콜백"""
        stats.record_message("orderbook")
        stats.record_parse(True, snapshot)
        
        logger.info(
            f"[D83-2 DEBUG] Snapshot received: {snapshot.symbol}, "
            f"bids={len(snapshot.bids)}, asks={len(snapshot.asks)}"
        )
    
    # BinanceWebSocketAdapter 생성
    symbol = "BTCUSDT"
    adapter = BinanceWebSocketAdapter(
        symbols=[symbol.lower()],
        callback=on_snapshot,
        depth="20",
        interval="100ms",
        heartbeat_interval=30.0,
        timeout=10.0,
    )
    
    try:
        logger.info(f"[D83-2 DEBUG] Connecting to Binance WebSocket...")
        logger.info(f"[D83-2 DEBUG] Symbol: {symbol}")
        logger.info(f"[D83-2 DEBUG] Duration: {duration_seconds}초")
        logger.info("")
        
        # 연결
        await adapter.connect()
        logger.info(f"[D83-2 DEBUG] Connected successfully")
        
        # 구독
        channels = [f"{symbol.lower()}@depth20@100ms"]
        logger.info(f"[D83-2 DEBUG] Subscribing to: {channels}")
        await adapter.subscribe(channels)
        logger.info(f"[D83-2 DEBUG] Subscription sent")
        logger.info("")
        
        # 메시지 수신 (duration_seconds 동안)
        logger.info(f"[D83-2 DEBUG] Listening for messages ({duration_seconds}초)...")
        logger.info("")
        
        # receive_loop를 타임아웃과 함께 실행
        try:
            await asyncio.wait_for(
                adapter.receive_loop(),
                timeout=duration_seconds
            )
        except asyncio.TimeoutError:
            logger.info(f"[D83-2 DEBUG] {duration_seconds}초 경과, 종료")
        
        # 연결 종료
        await adapter.disconnect()
        logger.info(f"[D83-2 DEBUG] Disconnected")
        
    except Exception as e:
        logger.error(f"[D83-2 DEBUG] Error: {e}", exc_info=True)
    
    finally:
        # 통계 출력
        logger.info("")
        stats.print_summary()
        
        # 결과 판단
        logger.info("")
        logger.info("=" * 80)
        logger.info("[D83-2 DEBUG] 결과 판단")
        logger.info("=" * 80)
        
        if stats.messages_received == 0:
            logger.error("❌ FAIL: 메시지 수신 없음")
            logger.error("원인 가능성:")
            logger.error("  1. Binance WebSocket 엔드포인트 오류")
            logger.error("  2. 구독 메시지 포맷 불일치")
            logger.error("  3. 네트워크 연결 문제")
        elif stats.parse_failures > 0:
            logger.warning(f"⚠️  WARNING: 파싱 실패 {stats.parse_failures}건")
        else:
            logger.info("✅ SUCCESS: Binance WebSocket 정상 작동")
            logger.info(f"  - {stats.messages_received}개 메시지 수신")
            logger.info(f"  - {stats.parse_success}개 스냅샷 파싱")
        
        logger.info("=" * 80)


def main():
    """메인 함수"""
    logger.info("=" * 80)
    logger.info("[D83-2] Binance WebSocket 독립 디버그 시작")
    logger.info("=" * 80)
    logger.info("")
    
    # 30초 테스트 실행
    asyncio.run(test_binance_websocket(duration_seconds=30))
    
    logger.info("")
    logger.info("[D83-2] 디버그 종료")


if __name__ == "__main__":
    main()
