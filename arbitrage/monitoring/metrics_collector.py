"""
D50: Metrics Collector

루프 메트릭을 수집하고 관리한다.

D54: Async queue 지원 추가 (멀티심볼 v2.0 기반)
D55: Async queue processing loop 추가 (완전 비동기 전환)
D57: Per-symbol metrics structure 준비 (symbol 파라미터 추가)
D58: Symbol-aware guard metrics 준비 (per-symbol guard stats)
"""

import asyncio
import logging
import time
from collections import deque
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class MetricsCollector:
    """
    메트릭 수집 및 관리
    
    책임:
    - 루프 실행 시간, 체결 횟수, 스프레드 등 수집
    - 최근 N개 루프 기록 유지
    - 평균/최대/최소 계산
    - 데이터 소스 및 WS 상태 추적
    """
    
    def __init__(self, buffer_size: int = 200):
        """
        Args:
            buffer_size: 최근 N개 루프 기록 유지 (기본값: 200 = 3.3분 @ 1루프/초)
            D53: 최적화 - 300 → 200으로 감소 (메모리 절감)
        """
        self.buffer_size = buffer_size
        
        # 루프 메트릭 버퍼
        self.loop_times: deque = deque(maxlen=buffer_size)
        self.trades_opened: deque = deque(maxlen=buffer_size)
        self.spreads: deque = deque(maxlen=buffer_size)
        
        # 상태 정보
        self.data_source: str = "rest"
        self.ws_connected: bool = False
        self.ws_reconnect_count: int = 0
        
        # 누적 통계
        self.trades_opened_total: int = 0
        self.start_time: float = time.time()
        
        # D55: Async queue for metrics collection
        self._metrics_queue: Optional[asyncio.Queue] = None
        self._processing_task: Optional[asyncio.Task] = None
        
        # D58: Symbol-aware guard metrics
        self.per_symbol_guard_rejected: Dict[str, int] = {}  # {symbol: rejected_count}
        self.per_symbol_guard_allowed: Dict[str, int] = {}  # {symbol: allowed_count}
        self.per_symbol_guard_loss: Dict[str, float] = {}  # {symbol: total_loss}
    
    def update_loop_metrics(
        self,
        loop_time_ms: float,
        trades_opened: int,
        spread_bps: float,
        data_source: str,
        ws_connected: bool = False,
        ws_reconnects: int = 0,
        symbol: Optional[str] = None,  # D57: Multi-Symbol support
    ) -> None:
        """
        루프 메트릭 업데이트
        D53: 최적화 - dict 할당 제거, 직접 파라미터 사용
        D57: symbol 파라미터 추가 (per-symbol metrics 준비)
        
        Args:
            loop_time_ms: 루프 실행 시간 (ms)
            trades_opened: 이번 루프에서 체결된 거래 수
            spread_bps: 스프레드 (basis points)
            data_source: 데이터 소스 ("rest" 또는 "ws")
            ws_connected: WebSocket 연결 상태
            ws_reconnects: WebSocket 재연결 횟수
            symbol: D57 심볼 (멀티심볼 모드에서 사용)
        """
        # 루프 메트릭 버퍼에 추가
        self.loop_times.append(loop_time_ms)
        self.trades_opened.append(trades_opened)
        self.spreads.append(spread_bps)
        
        # 상태 정보 업데이트 (D53: 직접 할당)
        self.data_source = data_source
        self.ws_connected = ws_connected
        self.ws_reconnect_count = ws_reconnects
        
        # 누적 통계 업데이트
        self.trades_opened_total += trades_opened
        
        log_msg = (
            f"[D57_METRICS] loop_time={loop_time_ms:.2f}ms, "
            f"trades={trades_opened}, spread={spread_bps:.2f}bps, "
            f"data_source={data_source}"
        )
        if symbol:
            log_msg += f", symbol={symbol}"
        
        logger.debug(log_msg)
    
    def get_metrics(self) -> Dict[str, Any]:
        """
        현재 메트릭 반환
        
        Returns:
            메트릭 dict
        """
        loop_times = list(self.loop_times)
        trades_list = list(self.trades_opened)
        spreads = list(self.spreads)
        
        # 평균 계산
        loop_time_avg = sum(loop_times) / len(loop_times) if loop_times else 0.0
        spread_avg = sum(spreads) / len(spreads) if spreads else 0.0
        
        # 최대/최소 계산
        loop_time_max = max(loop_times) if loop_times else 0.0
        loop_time_min = min(loop_times) if loop_times else 0.0
        
        # 최근 1분 체결 횟수 (최근 60개 루프 기준)
        trades_recent = sum(trades_list[-60:]) if trades_list else 0
        
        # 업타임 계산
        uptime_seconds = time.time() - self.start_time
        
        return {
            # 루프 시간 메트릭
            "loop_time_ms": loop_times[-1] if loop_times else 0.0,
            "loop_time_avg_ms": loop_time_avg,
            "loop_time_max_ms": loop_time_max,
            "loop_time_min_ms": loop_time_min,
            
            # 체결 메트릭
            "trades_opened_total": self.trades_opened_total,
            "trades_opened_recent": trades_recent,
            
            # 스프레드 메트릭
            "spread_bps": spreads[-1] if spreads else 0.0,
            "spread_avg_bps": spread_avg,
            
            # 상태 정보
            "data_source": self.data_source,
            "ws_connected": self.ws_connected,
            "ws_reconnect_count": self.ws_reconnect_count,
            
            # 시스템 정보
            "uptime_seconds": uptime_seconds,
            "buffer_size": self.buffer_size,
            "buffer_usage": len(loop_times),
        }
    
    def get_health(self) -> Dict[str, Any]:
        """
        헬스 체크 정보 반환
        
        Returns:
            헬스 체크 dict
        """
        return {
            "status": "ok",
            "data_source": self.data_source,
            "uptime_seconds": time.time() - self.start_time,
            "ws_connected": self.ws_connected,
        }
    
    def reset(self) -> None:
        """
        메트릭 리셋 (테스트용)
        """
        self.loop_times.clear()
        self.trades_opened.clear()
        self.spreads.clear()
        self.trades_opened_total = 0
        self.start_time = time.time()
        logger.info("[D50_METRICS] Metrics reset")
    
    async def aupdate_loop_metrics(
        self,
        loop_time_ms: float,
        trades_opened: int,
        spread_bps: float,
        data_source: str,
        ws_connected: bool = False,
        ws_reconnects: int = 0,
        symbol: Optional[str] = None,  # D57: Multi-Symbol support
    ) -> None:
        """
        D54: Async wrapper for update_loop_metrics
        D57: symbol 파라미터 추가 (per-symbol metrics 준비)
        
        멀티심볼 병렬 처리를 위한 async 인터페이스.
        내부적으로는 sync 메서드를 호출하되, 추후 async queue 기반 수집 대비.
        
        Args:
            loop_time_ms: 루프 실행 시간 (ms)
            trades_opened: 이번 루프에서 체결된 거래 수
            spread_bps: 스프레드 (basis points)
            data_source: 데이터 소스 ("rest" 또는 "ws")
            ws_connected: WebSocket 연결 상태
            ws_reconnects: WebSocket 재연결 횟수
            symbol: D57 심볼 (멀티심볼 모드에서 사용)
        """
        # 현재는 sync 메서드를 event loop에서 실행
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            self.update_loop_metrics,
            loop_time_ms,
            trades_opened,
            spread_bps,
            data_source,
            ws_connected,
            ws_reconnects,
            symbol,
        )
    
    async def astart_queue_processing(self) -> None:
        """
        D55: Start async queue processing loop
        
        메트릭을 비동기 큐에서 처리한다.
        """
        self._metrics_queue = asyncio.Queue()
        self._processing_task = asyncio.create_task(self._process_metrics_queue())
        logger.info("[D55_METRICS] Async queue processing started")
    
    async def astop_queue_processing(self) -> None:
        """
        D55: Stop async queue processing loop
        
        비동기 큐 처리를 종료한다.
        """
        if self._processing_task:
            self._processing_task.cancel()
            try:
                await self._processing_task
            except asyncio.CancelledError:
                pass
        self._metrics_queue = None
        logger.info("[D55_METRICS] Async queue processing stopped")
    
    async def aqueue_metrics(
        self,
        loop_time_ms: float,
        trades_opened: int,
        spread_bps: float,
        data_source: str,
        ws_connected: bool = False,
        ws_reconnects: int = 0,
    ) -> None:
        """
        D55: Queue metrics for async processing
        
        메트릭을 비동기 큐에 추가한다.
        """
        if self._metrics_queue is None:
            logger.warning("[D55_METRICS] Queue not initialized")
            return
        
        metric_data = {
            "loop_time_ms": loop_time_ms,
            "trades_opened": trades_opened,
            "spread_bps": spread_bps,
            "data_source": data_source,
            "ws_connected": ws_connected,
            "ws_reconnects": ws_reconnects,
        }
        
        await self._metrics_queue.put(metric_data)
    
    async def _process_metrics_queue(self) -> None:
        """
        D55: Process metrics from async queue
        
        비동기 큐에서 메트릭을 처리하는 루프.
        """
        while True:
            try:
                metric_data = await asyncio.wait_for(
                    self._metrics_queue.get(),
                    timeout=5.0,
                )
                
                # Sync 메서드로 메트릭 업데이트
                self.update_loop_metrics(
                    loop_time_ms=metric_data["loop_time_ms"],
                    trades_opened=metric_data["trades_opened"],
                    spread_bps=metric_data["spread_bps"],
                    data_source=metric_data["data_source"],
                    ws_connected=metric_data["ws_connected"],
                    ws_reconnects=metric_data["ws_reconnects"],
                )
                
                self._metrics_queue.task_done()
            
            except asyncio.TimeoutError:
                # 타임아웃은 정상 (큐가 비어있음)
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[D55_METRICS] Queue processing error: {e}")
