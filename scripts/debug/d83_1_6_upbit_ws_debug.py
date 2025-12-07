"""
D83-1.6: Upbit WebSocket 독립 디버그 스크립트

Upbit Public WebSocket API를 직접 테스트하여 메시지 수신 문제를 진단합니다.

목적:
- WebSocket 연결/구독/메시지 수신의 각 단계를 상세히 로깅
- Raw 메시지 형식 확인 (JSON/binary, 길이, 필드 구조)
- OrderBookSnapshot 파싱 검증
- 문제가 있는 지점 정확히 식별

Usage:
    python scripts/debug/d83_1_6_upbit_ws_debug.py [--duration SECONDS] [--symbol SYMBOL]
"""

import asyncio
import argparse
import logging
import sys
import time
from pathlib import Path

# arbitrage 모듈 import를 위한 경로 추가
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from arbitrage.exchanges.upbit_ws_adapter import UpbitWebSocketAdapter
from arbitrage.exchanges.base import OrderBookSnapshot


# 로깅 설정 (DEBUG 레벨)
logging.basicConfig(
    level=logging.DEBUG,
    format='[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
)
logger = logging.getLogger(__name__)


class DebugStats:
    """디버그 통계 수집"""
    
    def __init__(self):
        self.messages_received = 0
        self.snapshots_parsed = 0
        self.parse_failures = 0
        self.first_message_time = None
        self.last_message_time = None
        self.symbols_seen = set()
        self.message_types_seen = {}
    
    def on_message(self):
        """메시지 수신 시 호출"""
        self.messages_received += 1
        current_time = time.time()
        
        if self.first_message_time is None:
            self.first_message_time = current_time
        self.last_message_time = current_time
    
    def on_snapshot(self, snapshot: OrderBookSnapshot):
        """스냅샷 파싱 성공 시 호출"""
        self.snapshots_parsed += 1
        self.symbols_seen.add(snapshot.symbol)
    
    def on_parse_failure(self):
        """파싱 실패 시 호출"""
        self.parse_failures += 1
    
    def on_message_type(self, msg_type: str):
        """메시지 타입 집계"""
        self.message_types_seen[msg_type] = self.message_types_seen.get(msg_type, 0) + 1
    
    def print_summary(self):
        """통계 요약 출력"""
        logger.info("")
        logger.info("=" * 80)
        logger.info("[D83-1.6_DEBUG] 디버그 세션 통계")
        logger.info("=" * 80)
        logger.info(f"수신 메시지 수: {self.messages_received}")
        logger.info(f"파싱 성공 스냅샷: {self.snapshots_parsed}")
        logger.info(f"파싱 실패: {self.parse_failures}")
        
        if self.first_message_time and self.last_message_time:
            duration = self.last_message_time - self.first_message_time
            rate = self.messages_received / duration if duration > 0 else 0
            logger.info(f"첫 메시지 수신: {self.first_message_time:.3f}")
            logger.info(f"마지막 메시지 수신: {self.last_message_time:.3f}")
            logger.info(f"메시지 수신 간격: {duration:.1f}초")
            logger.info(f"평균 수신 속도: {rate:.2f} msg/s")
        else:
            logger.warning("메시지 수신 없음!")
        
        if self.symbols_seen:
            logger.info(f"수신된 심볼: {sorted(self.symbols_seen)}")
        else:
            logger.warning("파싱된 심볼 없음!")
        
        if self.message_types_seen:
            logger.info(f"메시지 타입 분포: {self.message_types_seen}")
        
        logger.info("=" * 80)


async def main(duration: int = 60, symbol: str = "KRW-BTC"):
    """
    메인 디버그 루프
    
    Args:
        duration: 실행 시간 (초)
        symbol: 테스트할 심볼
    """
    logger.info("")
    logger.info("=" * 80)
    logger.info("[D83-1.6_DEBUG] Upbit WebSocket 독립 디버그 시작")
    logger.info("=" * 80)
    logger.info(f"테스트 심볼: {symbol}")
    logger.info(f"실행 시간: {duration}초")
    logger.info(f"Upbit WebSocket URL: wss://api.upbit.com/websocket/v1")
    logger.info("=" * 80)
    logger.info("")
    
    stats = DebugStats()
    
    def on_snapshot_callback(snapshot: OrderBookSnapshot):
        """스냅샷 콜백 (통계 수집)"""
        stats.on_message()
        stats.on_snapshot(snapshot)
        
        # 첫 5개 메시지는 상세 로그
        if stats.messages_received <= 5:
            logger.info(
                f"[D83-1.6_DEBUG] 스냅샷 수신 #{stats.messages_received}: "
                f"symbol={snapshot.symbol}, bids={len(snapshot.bids)}, "
                f"asks={len(snapshot.asks)}, timestamp={snapshot.timestamp:.3f}"
            )
            if snapshot.bids and snapshot.asks:
                logger.info(
                    f"[D83-1.6_DEBUG]   Top bid: {snapshot.bids[0][0]:.2f} x {snapshot.bids[0][1]:.4f}"
                )
                logger.info(
                    f"[D83-1.6_DEBUG]   Top ask: {snapshot.asks[0][0]:.2f} x {snapshot.asks[0][1]:.4f}"
                )
        elif stats.messages_received % 10 == 0:
            # 10번마다 간단 로그
            logger.info(
                f"[D83-1.6_DEBUG] 진행 중... 메시지 수신: {stats.messages_received}"
            )
    
    # WebSocket Adapter 생성
    logger.info("[D83-1.6_DEBUG] UpbitWebSocketAdapter 생성 중...")
    adapter = UpbitWebSocketAdapter(
        symbols=[symbol],
        callback=on_snapshot_callback,
        heartbeat_interval=30.0,
        timeout=10.0,
    )
    
    try:
        # 1. 연결
        logger.info("[D83-1.6_DEBUG] STEP 1: WebSocket 연결 시도...")
        await adapter.connect()
        logger.info("[D83-1.6_DEBUG] STEP 1: 연결 성공!")
        
        # 2. 구독
        logger.info(f"[D83-1.6_DEBUG] STEP 2: {symbol} orderbook 구독 시도...")
        await adapter.subscribe([symbol])
        logger.info("[D83-1.6_DEBUG] STEP 2: 구독 성공!")
        
        # 3. receive_loop를 백그라운드 태스크로 실행
        logger.info(f"[D83-1.6_DEBUG] STEP 3: receive_loop 시작 (duration={duration}초)...")
        receive_task = asyncio.create_task(adapter.receive_loop())
        
        # duration 동안 대기
        await asyncio.sleep(duration)
        
        # 4. 종료
        logger.info("[D83-1.6_DEBUG] STEP 4: 테스트 완료, 연결 종료 중...")
        adapter.is_running = False
        await adapter.disconnect()
        
        # receive_task 취소
        if not receive_task.done():
            receive_task.cancel()
            try:
                await receive_task
            except asyncio.CancelledError:
                pass
        
        logger.info("[D83-1.6_DEBUG] STEP 4: 연결 종료 완료")
    
    except Exception as e:
        logger.error(f"[D83-1.6_DEBUG] 예외 발생: {e}", exc_info=True)
    
    finally:
        # 통계 출력
        stats.print_summary()
        
        # 진단 결과
        logger.info("")
        logger.info("=" * 80)
        logger.info("[D83-1.6_DEBUG] 진단 결과")
        logger.info("=" * 80)
        
        if stats.messages_received == 0:
            logger.error("❌ 메시지 수신 실패!")
            logger.error("   원인 가능성:")
            logger.error("   1. Upbit WebSocket 구독 포맷 불일치")
            logger.error("   2. 네트워크/방화벽 차단")
            logger.error("   3. WebSocket timeout 설정 문제")
            logger.error("   4. receive_loop() 로직 문제")
        elif stats.snapshots_parsed == 0:
            logger.error("❌ 메시지는 수신되었으나 파싱 실패!")
            logger.error("   원인 가능성:")
            logger.error("   1. Upbit 메시지 포맷 변경")
            logger.error("   2. Binary/JSON 인코딩 불일치")
            logger.error("   3. 파싱 로직 버그")
        else:
            logger.info(f"✅ 성공! {stats.messages_received}개 메시지 수신, {stats.snapshots_parsed}개 스냅샷 파싱")
            logger.info("   → Upbit WebSocket 자체는 정상 작동")
            logger.info("   → 문제는 UpbitL2WebSocketProvider 또는 Runner 통합 단계에 있을 가능성")
        
        logger.info("=" * 80)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="D83-1.6: Upbit WebSocket 독립 디버그")
    parser.add_argument(
        "--duration",
        type=int,
        default=60,
        help="실행 시간 (초), 기본값=60",
    )
    parser.add_argument(
        "--symbol",
        type=str,
        default="KRW-BTC",
        help="테스트 심볼, 기본값=KRW-BTC",
    )
    
    args = parser.parse_args()
    
    try:
        asyncio.run(main(duration=args.duration, symbol=args.symbol))
    except KeyboardInterrupt:
        logger.info("\n[D83-1.6_DEBUG] 사용자에 의해 중단됨")
