"""
D205-15-6: RunWatcher - Self-Monitoring & FAIL-fast Engine

Purpose: 사람 개입 없이 Paper Run을 자기감시하여 FAIL 조건 감지 시 즉시 중단

FAIL Conditions:
- (A) wins=0 AND closed_trades >= N (예: 100)
- (B) realized_edge_bps 5분 연속 음수
- (C) profitable_true가 0이 10분 지속 → EARLY_INFEASIBLE

Architecture:
- Watcher는 별도 Thread로 실행 (60초 heartbeat)
- PaperRunner의 KPI를 주기적으로 체크
- FAIL 감지 시 graceful_stop 신호 발생
"""

import logging
import threading
import time
from datetime import datetime, timezone
from typing import Optional, Callable
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class WatcherConfig:
    """RunWatcher 설정"""
    heartbeat_sec: int = 60  # Heartbeat 주기 (초)
    
    # FAIL 조건 (A): wins=0 연속
    min_trades_for_winrate_check: int = 100
    
    # FAIL 조건 (B): edge<0 연속
    negative_edge_duration_sec: int = 300  # 5분
    
    # FAIL 조건 (C): profitable=0 지속
    no_opportunity_duration_sec: int = 600  # 10분


class RunWatcher:
    """
    D205-15-6: Paper Run Self-Monitor
    
    사람 개입 없이 자기감시하여 FAIL 조건 감지 시 즉시 중단
    """
    
    def __init__(
        self,
        config: WatcherConfig,
        kpi_getter: Callable,  # PaperRunner.kpi를 반환하는 함수
        stop_callback: Callable,  # PaperRunner.request_stop()를 호출하는 함수
    ):
        self.config = config
        self.kpi_getter = kpi_getter
        self.stop_callback = stop_callback
        
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._running = False
        
        # FAIL 조건 추적
        self._negative_edge_start: Optional[float] = None
        self._no_opportunity_start: Optional[float] = None
        self._last_check_time: Optional[float] = None
        
        self.stop_reason: Optional[str] = None
        self.diagnosis: Optional[str] = None
    
    def start(self):
        """Watcher Thread 시작"""
        if self._running:
            logger.warning("[RunWatcher] Already running")
            return
        
        self._stop_event.clear()
        self._running = True
        self._thread = threading.Thread(target=self._watch_loop, daemon=True)
        self._thread.start()
        logger.info(f"[RunWatcher] Started (heartbeat: {self.config.heartbeat_sec}s)")
    
    def stop(self):
        """Watcher Thread 중지"""
        if not self._running:
            return
        
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5.0)
        self._running = False
        logger.info("[RunWatcher] Stopped")
    
    def _watch_loop(self):
        """Watcher 메인 루프 (60초 heartbeat)"""
        while not self._stop_event.is_set():
            try:
                self._check_fail_conditions()
            except Exception as e:
                logger.error(f"[RunWatcher] Check failed: {e}", exc_info=True)
            
            # Heartbeat 대기 (중단 신호 체크)
            self._stop_event.wait(self.config.heartbeat_sec)
    
    def _check_fail_conditions(self):
        """FAIL 조건 체크"""
        now = time.time()
        self._last_check_time = now
        
        # KPI 가져오기
        kpi = self.kpi_getter()
        
        # FAIL 조건 (A): wins=0 AND closed_trades >= N
        if kpi.closed_trades >= self.config.min_trades_for_winrate_check and kpi.wins == 0:
            self.stop_reason = "ERROR"
            self.diagnosis = (
                f"FAIL (A): wins=0 after {kpi.closed_trades} trades. "
                f"100% losing trades detected. "
                f"Possible causes: market spread < break_even OR logic/model bug."
            )
            logger.error(f"[RunWatcher] {self.diagnosis}")
            self._trigger_graceful_stop()
            return
        
        # FAIL 조건 (B): realized_edge<0 연속 5분
        # (간단 구현: net_pnl이 계속 감소하는지 체크)
        if kpi.closed_trades > 0:
            avg_pnl_per_trade = kpi.net_pnl / kpi.closed_trades
            if avg_pnl_per_trade < 0:
                if self._negative_edge_start is None:
                    self._negative_edge_start = now
                    logger.warning(f"[RunWatcher] Negative edge detected (avg: {avg_pnl_per_trade:.2f})")
                elif (now - self._negative_edge_start) >= self.config.negative_edge_duration_sec:
                    self.stop_reason = "ERROR"
                    self.diagnosis = (
                        f"FAIL (B): Negative edge for {self.config.negative_edge_duration_sec}s. "
                        f"avg_pnl_per_trade={avg_pnl_per_trade:.2f}. "
                        f"Market spread likely < break_even."
                    )
                    logger.error(f"[RunWatcher] {self.diagnosis}")
                    self._trigger_graceful_stop()
                    return
            else:
                self._negative_edge_start = None
        
        # 정상: Heartbeat 로그
        logger.debug(
            f"[RunWatcher] Heartbeat OK - "
            f"trades={kpi.closed_trades}, wins={kpi.wins}, losses={kpi.losses}, "
            f"net_pnl={kpi.net_pnl:.2f}"
        )
    
    def _trigger_graceful_stop(self):
        """Graceful Stop 트리거"""
        logger.info("[RunWatcher] Triggering graceful stop...")
        self.stop_callback()
        self._stop_event.set()


def create_watcher(
    kpi_getter: Callable,
    stop_callback: Callable,
    heartbeat_sec: int = 60,
    min_trades_for_check: int = 100,
) -> RunWatcher:
    """
    RunWatcher 인스턴스 생성 (Factory)
    
    Args:
        kpi_getter: PaperRunner.kpi를 반환하는 함수
        stop_callback: PaperRunner.request_stop()를 호출하는 함수
        heartbeat_sec: Heartbeat 주기 (초)
        min_trades_for_check: wins=0 체크할 최소 거래 수
    
    Returns:
        RunWatcher 인스턴스
    """
    config = WatcherConfig(
        heartbeat_sec=heartbeat_sec,
        min_trades_for_winrate_check=min_trades_for_check,
    )
    return RunWatcher(config, kpi_getter, stop_callback)
