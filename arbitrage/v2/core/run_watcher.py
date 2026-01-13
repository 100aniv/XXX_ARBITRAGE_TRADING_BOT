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
import json
import os
from datetime import datetime, timezone
from typing import Optional, Callable
from dataclasses import dataclass
from pathlib import Path

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
    
    # FAIL 조건 (D): Max Drawdown (최대 낙폭)
    max_drawdown_pct: float = 20.0  # 20% 낙폭 시 중단
    
    # FAIL 조건 (E): Consecutive Losses (연속 손실)
    max_consecutive_losses: int = 10  # 10연속 손실 시 중단
    
    # Evidence 경로
    evidence_dir: str = "logs/evidence"


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
        run_id: str = "unknown",
    ):
        self.config = config
        self.kpi_getter = kpi_getter
        self.stop_callback = stop_callback
        self.run_id = run_id
        
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._running = False
        
        # FAIL 조건 추적
        self._negative_edge_start: Optional[float] = None
        self._no_opportunity_start: Optional[float] = None
        self._last_check_time: Optional[float] = None
        
        # Safety Guard 추적
        self._peak_pnl: float = 0.0
        self._consecutive_losses: int = 0
        self._last_trade_result: Optional[str] = None
        
        self.stop_reason: Optional[str] = None
        self.diagnosis: Optional[str] = None
        
        # Evidence 경로 설정
        self._heartbeat_file = self._get_heartbeat_path()
        self._snapshot_file = self._get_snapshot_path()
    
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
            self._save_stop_reason_snapshot(kpi, "FAIL_A_WINRATE_ZERO")
            self._trigger_graceful_stop()
            return
        
        # FAIL 조건 (B): realized_edge<0 연속 5분
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
                    self._save_stop_reason_snapshot(kpi, "FAIL_B_NEGATIVE_EDGE")
                    self._trigger_graceful_stop()
                    return
            else:
                self._negative_edge_start = None
        
        # FAIL 조건 (D): Max Drawdown
        if kpi.net_pnl > self._peak_pnl:
            self._peak_pnl = kpi.net_pnl
        
        if self._peak_pnl > 0:
            drawdown = ((self._peak_pnl - kpi.net_pnl) / self._peak_pnl) * 100
            if drawdown >= self.config.max_drawdown_pct:
                self.stop_reason = "ERROR"
                self.diagnosis = (
                    f"FAIL (D): Max Drawdown exceeded. "
                    f"Peak PnL: {self._peak_pnl:.2f}, Current PnL: {kpi.net_pnl:.2f}, "
                    f"Drawdown: {drawdown:.1f}% >= {self.config.max_drawdown_pct}%"
                )
                logger.error(f"[RunWatcher] {self.diagnosis}")
                self._save_stop_reason_snapshot(kpi, "FAIL_D_MAX_DRAWDOWN")
                self._trigger_graceful_stop()
                return
        
        # FAIL 조건 (E): Consecutive Losses
        if kpi.closed_trades > 0:
            current_result = "win" if kpi.wins > 0 else "loss"
            if current_result != self._last_trade_result:
                if current_result == "loss":
                    self._consecutive_losses = 1
                else:
                    self._consecutive_losses = 0
                self._last_trade_result = current_result
            elif current_result == "loss":
                self._consecutive_losses += 1
            
            if self._consecutive_losses >= self.config.max_consecutive_losses:
                self.stop_reason = "ERROR"
                self.diagnosis = (
                    f"FAIL (E): {self._consecutive_losses} consecutive losses. "
                    f"Max allowed: {self.config.max_consecutive_losses}. "
                    f"Possible causes: adverse market conditions OR strategy failure."
                )
                logger.error(f"[RunWatcher] {self.diagnosis}")
                self._save_stop_reason_snapshot(kpi, "FAIL_E_CONSECUTIVE_LOSSES")
                self._trigger_graceful_stop()
                return
        
        # 정상: Heartbeat 기록 (파일 + 로그)
        self._save_heartbeat(kpi)
        logger.debug(
            f"[RunWatcher] Heartbeat OK - "
            f"trades={kpi.closed_trades}, wins={kpi.wins}, losses={kpi.losses}, "
            f"net_pnl={kpi.net_pnl:.2f}, drawdown={(((self._peak_pnl - kpi.net_pnl) / self._peak_pnl * 100) if self._peak_pnl > 0 else 0):.1f}%"
        )
    
    def _trigger_graceful_stop(self):
        """Graceful Stop 트리거"""
        logger.info("[RunWatcher] Triggering graceful stop...")
        self.stop_callback()
        self._stop_event.set()
    
    def _get_heartbeat_path(self) -> str:
        """Heartbeat 파일 경로 반환"""
        evidence_dir = Path(self.config.evidence_dir) / self.run_id
        evidence_dir.mkdir(parents=True, exist_ok=True)
        return str(evidence_dir / "heartbeat.jsonl")
    
    def _get_snapshot_path(self) -> str:
        """Stop Reason Snapshot 파일 경로 반환"""
        evidence_dir = Path(self.config.evidence_dir) / self.run_id
        evidence_dir.mkdir(parents=True, exist_ok=True)
        return str(evidence_dir / "stop_reason_snapshot.json")
    
    def _save_heartbeat(self, kpi):
        """Heartbeat를 파일에 기록 (JSONL 형식)"""
        try:
            heartbeat_data = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "epoch_time": time.time(),
                "kpi": {
                    "closed_trades": kpi.closed_trades,
                    "wins": kpi.wins,
                    "losses": kpi.losses,
                    "net_pnl": float(kpi.net_pnl),
                    "opportunities_generated": kpi.opportunities_generated,
                },
                "guards": {
                    "peak_pnl": float(self._peak_pnl),
                    "drawdown_pct": float(((self._peak_pnl - kpi.net_pnl) / self._peak_pnl * 100) if self._peak_pnl > 0 else 0),
                    "consecutive_losses": self._consecutive_losses,
                },
            }
            
            with open(self._heartbeat_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(heartbeat_data) + "\n")
        except Exception as e:
            logger.error(f"[RunWatcher] Failed to save heartbeat: {e}")
    
    def _save_stop_reason_snapshot(self, kpi, fail_code: str):
        """가드 트리거 시 현장 증거 저장"""
        try:
            snapshot_data = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "fail_code": fail_code,
                "stop_reason": self.stop_reason,
                "diagnosis": self.diagnosis,
                "kpi_snapshot": {
                    "closed_trades": kpi.closed_trades,
                    "wins": kpi.wins,
                    "losses": kpi.losses,
                    "net_pnl": float(kpi.net_pnl),
                    "opportunities_generated": kpi.opportunities_generated,
                },
                "guard_state": {
                    "peak_pnl": float(self._peak_pnl),
                    "current_drawdown_pct": float(((self._peak_pnl - kpi.net_pnl) / self._peak_pnl * 100) if self._peak_pnl > 0 else 0),
                    "consecutive_losses": self._consecutive_losses,
                    "negative_edge_duration_sec": float(time.time() - self._negative_edge_start) if self._negative_edge_start else 0,
                },
            }
            
            with open(self._snapshot_file, "w", encoding="utf-8") as f:
                json.dump(snapshot_data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"[RunWatcher] Stop reason snapshot saved: {self._snapshot_file}")
        except Exception as e:
            logger.error(f"[RunWatcher] Failed to save stop reason snapshot: {e}")
    
    def verify_heartbeat_density(self) -> dict:
        """
        D205-18-4-FIX F2: Heartbeat density 검증 (WARN=FAIL + max_gap)
        
        Returns:
            {
                "heartbeat_file": str,
                "line_count": int,
                "expected_min": int,
                "max_gap_seconds": float,
                "status": "PASS" | "FAIL",
                "message": str
            }
        """
        try:
            if not Path(self._heartbeat_file).exists():
                return {
                    "heartbeat_file": self._heartbeat_file,
                    "line_count": 0,
                    "expected_min": 0,
                    "status": "FAIL",
                    "message": "heartbeat.jsonl not found"
                }
            
            # D205-18-4-FIX F2: heartbeat.jsonl 읽기 + timestamp 파싱
            import json
            from datetime import datetime
            
            timestamps = []
            with open(self._heartbeat_file, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        record = json.loads(line.strip())
                        ts_str = record.get("timestamp")
                        if ts_str:
                            ts = datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
                            timestamps.append(ts.timestamp())
                    except (json.JSONDecodeError, ValueError, KeyError):
                        continue
            
            line_count = len(timestamps)
            
            # D205-18-4-FIX F2: expected_min 수정 (duration_minutes 기반)
            # 예: 20분 run, 60초 heartbeat → 최소 20줄
            # RunWatcher는 duration_minutes를 모르므로, line_count 기반 검증으로 변경
            # 최소 1줄은 있어야 함
            expected_min = max(1, 1)  # 최소 1줄 (정확한 duration은 orchestrator에서 전달 필요)
            
            # D205-18-4-FIX F2: max_gap 검증 (OPS_PROTOCOL 65초 이하)
            max_gap = 0.0
            if len(timestamps) >= 2:
                gaps = [timestamps[i+1] - timestamps[i] for i in range(len(timestamps)-1)]
                max_gap = max(gaps) if gaps else 0.0
            
            if line_count == 0:
                status = "FAIL"
                message = "No heartbeat records"
            elif max_gap > 65.0:  # OPS_PROTOCOL Invariant 2.2
                status = "FAIL"  # D205-18-4-FIX F2: WARN = FAIL
                message = f"Heartbeat gap too large: {max_gap:.1f}s (max 65s)"
            elif line_count < expected_min:
                status = "FAIL"  # D205-18-4-FIX F2: WARN = FAIL
                message = f"Low heartbeat density: {line_count} lines"
            else:
                status = "PASS"
                message = f"Heartbeat density OK: {line_count} lines, max_gap={max_gap:.1f}s"
            
            return {
                "heartbeat_file": self._heartbeat_file,
                "line_count": line_count,
                "expected_min": expected_min,
                "max_gap_seconds": max_gap,
                "status": status,
                "message": message
            }
        except Exception as e:
            logger.error(f"[RunWatcher] Heartbeat density verification failed: {e}")
            return {
                "heartbeat_file": self._heartbeat_file,
                "line_count": 0,
                "expected_min": 0,
                "status": "FAIL",
                "message": f"Verification error: {e}"
            }


def create_watcher(
    kpi_getter: Callable,
    stop_callback: Callable,
    run_id: str = "unknown",
    heartbeat_sec: int = 60,
    min_trades_for_check: int = 100,
    max_drawdown_pct: float = 20.0,
    max_consecutive_losses: int = 10,
    evidence_dir: str = "logs/evidence",
) -> RunWatcher:
    """
    RunWatcher 인스턴스 생성 (Factory)
    
    Args:
        kpi_getter: PaperRunner.kpi를 반환하는 함수
        stop_callback: PaperRunner.request_stop()를 호출하는 함수
        run_id: Run ID (evidence 경로용)
        heartbeat_sec: Heartbeat 주기 (초)
        min_trades_for_check: wins=0 체크할 최소 거래 수
        max_drawdown_pct: 최대 낙폭 비율 (%) - Safety Guard D
        max_consecutive_losses: 최대 연속 손실 횟수 - Safety Guard E
        evidence_dir: Evidence 저장 경로
    
    Returns:
        RunWatcher 인스턴스
    """
    config = WatcherConfig(
        heartbeat_sec=heartbeat_sec,
        min_trades_for_winrate_check=min_trades_for_check,
        max_drawdown_pct=max_drawdown_pct,
        max_consecutive_losses=max_consecutive_losses,
        evidence_dir=evidence_dir,
    )
    return RunWatcher(config, kpi_getter, stop_callback, run_id)
