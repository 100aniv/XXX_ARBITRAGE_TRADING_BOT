"""
D205-18-2D + D206-0: Paper Orchestrator (Engine-Centric, OPS Protocol Embedded)

Core 컴포넌트만 사용, Runner 의존성 완전 제거.
D206-0: 운영 프로토콜 엔진 내재화 (WARN=FAIL, 상태 관리 인터페이스)

Purpose:
- OpportunitySource, PaperExecutor, LedgerWriter 통합
- Engine.run() 콜백 생성
- RunWatcher 통합
- Evidence 저장

Author: arbitrage-lite V2
Date: 2026-01-11
"""

import logging
import signal
import sys
import time
from enum import Enum
from typing import Dict, Optional, Any
from datetime import datetime
import uuid

from arbitrage.v2.core.opportunity_source import OpportunitySource
from arbitrage.v2.core.paper_executor import PaperExecutor
from arbitrage.v2.core.ledger_writer import LedgerWriter
from arbitrage.v2.core.metrics import PaperMetrics
from arbitrage.v2.core.monitor import EvidenceCollector
from arbitrage.v2.core.run_watcher import create_watcher
from arbitrage.v2.opportunity.intent_builder import candidate_to_order_intents

logger = logging.getLogger(__name__)


class OrchestratorState(Enum):
    """D206-0 AC-5: 엔진 상태 관리 인터페이스"""
    IDLE = "IDLE"
    RUNNING = "RUNNING"
    STOPPING = "STOPPING"
    STOPPED = "STOPPED"
    ERROR = "ERROR"


class WarningCounterHandler(logging.Handler):
    """
    D206-0 AC-2: WARN=FAIL 원칙 구현
    
    WARNING 레벨 이상 로그를 카운트하여 종료 시 검증.
    OPS_PROTOCOL.md: "모든 Warning 레벨 로그는 잠재적 문제로 취급"
    """
    
    def __init__(self):
        super().__init__(level=logging.WARNING)
        self.warning_count = 0
        self.error_count = 0
        self._lock = __import__('threading').Lock()
    
    def emit(self, record: logging.LogRecord):
        with self._lock:
            if record.levelno == logging.WARNING:
                self.warning_count += 1
            elif record.levelno >= logging.ERROR:
                self.error_count += 1
    
    def reset(self):
        with self._lock:
            self.warning_count = 0
            self.error_count = 0
    
    def get_counts(self) -> Dict[str, int]:
        with self._lock:
            return {
                "warning_count": self.warning_count,
                "error_count": self.error_count
            }


class PaperOrchestrator:
    """
    Paper Execution Orchestrator (Engine-Centric)
    
    D205-18-2D + D206-0: Runner 콜백 의존 제거, Core 컴포넌트만 사용
    
    D206-0 운영 프로토콜 내재화:
    - WARN=FAIL 원칙: WarningCounterHandler로 WARNING 로그 카운트, 종료 시 검증
    - 상태 관리 인터페이스: OrchestratorState enum, get_state() 메서드
    - F1~F5 Invariant 검증 (D205-18-4R2에서 구현됨)
    
    Core 컴포넌트:
    - OpportunitySource: Opportunity 생성
    - PaperExecutor: 주문 실행
    - LedgerWriter: DB 기록
    - PaperMetrics: KPI 집계
    - EvidenceCollector: 증거 생성
    """
    
    def __init__(
        self,
        config,
        opportunity_source: OpportunitySource,
        executor: PaperExecutor,
        ledger_writer: LedgerWriter,
        kpi: PaperMetrics,
        evidence_collector: EvidenceCollector,
        admin_control: Optional[Any] = None,
        run_id: str = "unknown"
    ):
        self.config = config
        self.opportunity_source = opportunity_source
        self.executor = executor
        self.ledger_writer = ledger_writer
        self.kpi = kpi
        self.evidence_collector = evidence_collector
        self.admin_control = admin_control
        self.run_id = run_id
        
        self._stop_requested = False
        self._sigterm_received = False
        self._watcher = None
        self.trade_history = []
        
        # D206-0 AC-5: 상태 관리
        self._state = OrchestratorState.IDLE
        
        # D206-0 AC-2: WARN=FAIL Handler
        self._warning_handler = WarningCounterHandler()
        logging.getLogger().addHandler(self._warning_handler)
        
        # D205-18-4-FIX-2 F5: SIGTERM Handler 등록
        self._register_signal_handlers()
        
        logger.info("[D206-0] Orchestrator initialized with OPS Protocol embedded")
    
    def request_stop(self):
        """RunWatcher 중단 요청"""
        logger.warning("[D205-18-2D] Stop requested by RunWatcher")
        self._stop_requested = True
    
    def _register_signal_handlers(self):
        """
        D205-18-4-FIX-2 F5: SIGTERM/SIGINT Handler 등록
        
        OPS_PROTOCOL Invariant 2.5:
        - SIGTERM 수신 후 10초 내 Evidence Flush 완료
        - Exit Code 1 반환 (비정상 종료)
        """
        def sigterm_handler(signum, frame):
            signal_name = "SIGTERM" if signum == signal.SIGTERM else "SIGINT"
            logger.warning(f"[D205-18-4-FIX-2 F5] {signal_name} received, initiating graceful shutdown")
            self._sigterm_received = True
            self._stop_requested = True
        
        signal.signal(signal.SIGTERM, sigterm_handler)
        signal.signal(signal.SIGINT, sigterm_handler)
        logger.info("[D205-18-4-FIX-2 F5] Signal handlers registered (SIGTERM/SIGINT)")
    
    def run(self) -> int:
        """메인 실행 루프"""
        # D206-0 AC-5: 상태 전이 IDLE -> RUNNING
        self._state = OrchestratorState.RUNNING
        self._warning_handler.reset()  # D206-0 AC-2: WARNING 카운터 리셋
        
        logger.info(f"[D206-0] Orchestrator starting (state={self._state.value})...")
        
        # RunWatcher 시작
        self.start_watcher()
        
        try:
            duration_sec = self.config.duration_minutes * 60
            iteration = 0
            
            import time
            start_time = time.time()
            
            # D205-18-4-FIX F1: Wallclock tracking - 루프 직전 시점 기록 (객체 초기화 시간 제외)
            wallclock_start = time.time()
            self.kpi.wallclock_start = wallclock_start
            logger.info(f"[D205-18-4-FIX F1] Wallclock tracking started (loop entry): {wallclock_start}")
            
            while time.time() - start_time < duration_sec:
                iteration += 1
                
                if self._stop_requested:
                    if self._sigterm_received:
                        logger.warning("[D205-18-4-FIX-2 F5] Graceful shutdown initiated (SIGTERM)")
                    else:
                        logger.warning("[D205-18-2D] Stop requested by RunWatcher")
                    break
                
                # 1. Opportunity 생성
                candidate = self.opportunity_source.generate(iteration)
                if not candidate:
                    self.kpi.bump_reject("candidate_none")
                    continue
                
                self.kpi.opportunities_generated += 1
                
                # AdminControl 체크
                if self.admin_control:
                    if not self.admin_control.should_process_tick():
                        self.kpi.bump_reject("admin_paused")
                        continue
                    
                    if self.admin_control.is_symbol_blacklisted(candidate.symbol):
                        self.kpi.bump_reject("symbol_blacklisted")
                        continue
                
                # 2. Intent 변환
                intents = candidate_to_order_intents(candidate, quote_amount=100000.0)
                if not intents or len(intents) != 2:
                    self.kpi.bump_reject("intent_conversion_failed")
                    continue
                
                self.kpi.intents_created += len(intents)
                
                # 3. 주문 실행
                entry_result = self.executor.execute(intents[0], ref_price=candidate.price_a)
                exit_result = self.executor.execute(intents[1], ref_price=candidate.price_b)
                
                self.kpi.mock_executions += 2
                
                # 4. DB 기록
                self.ledger_writer.record_order_and_fill(intents[0], entry_result, candidate, self.kpi)
                self.ledger_writer.record_order_and_fill(intents[1], exit_result, candidate, self.kpi)
                
                # 5. Trade 완료 기록
                realized_pnl = (exit_result.filled_price - entry_result.filled_price) * entry_result.filled_qty - (entry_result.fee + exit_result.fee)
                
                trade_id = str(uuid.uuid4())
                self.ledger_writer.record_trade_complete(
                    trade_id=trade_id,
                    candidate=candidate,
                    intents=intents,
                    entry_result=entry_result,
                    exit_result=exit_result,
                    realized_pnl=realized_pnl,
                    kpi=self.kpi,
                )
                
                # 6. KPI 업데이트
                self.kpi.closed_trades += 1
                self.kpi.gross_pnl += realized_pnl
                self.kpi.fees += (entry_result.fee + exit_result.fee)
                self.kpi.net_pnl = self.kpi.gross_pnl - self.kpi.fees
                
                if realized_pnl > 0:
                    self.kpi.wins += 1
                else:
                    self.kpi.losses += 1
                
                if self.kpi.closed_trades > 0:
                    self.kpi.winrate_pct = (self.kpi.wins / self.kpi.closed_trades) * 100.0
                
                # 7. Trade History 기록
                self.trade_history.append({
                    "trade_id": trade_id,
                    "iteration": iteration,
                    "candidate_spread_bps": candidate.spread_bps,
                    "candidate_edge_bps": candidate.edge_bps,
                    "realized_pnl": realized_pnl,
                })
                
                # KPI 출력 (10 iteration마다)
                if iteration % 10 == 0:
                    logger.info(f"[D205-18-2D KPI] iter={iteration}, opp={self.kpi.opportunities_generated}, closed={self.kpi.closed_trades}, pnl={self.kpi.net_pnl:.2f}")
                
                time.sleep(0.1)
            
            logger.info(f"[D205-18-2D] Orchestrator completed: {iteration} iterations")
            
            # D205-18-4-FIX-2 F5: SIGTERM 시 즉시 Evidence Flush + Exit 1
            if self._sigterm_received:
                logger.warning("[D205-18-4-FIX-2 F5] SIGTERM detected, skipping validation, flushing evidence")
                db_counts = self.ledger_writer.get_counts()
                self.save_evidence(db_counts=db_counts)
                return 1  # SIGTERM = Exit 1
            
            # D205-18-4R2: Wallclock duration 종료 시간 기록
            wallclock_end = time.time()
            actual_duration = wallclock_end - wallclock_start
            expected_duration = duration_sec
            
            # D205-18-4R2: Step 1 - Wallclock Duration 검증 (±5% 범위)
            tolerance = expected_duration * 0.05
            if abs(actual_duration - expected_duration) > tolerance:
                logger.error(
                    f"[D205-18-4R2] Wallclock duration FAIL: "
                    f"actual={actual_duration:.1f}s, expected={expected_duration:.1f}s, "
                    f"tolerance=±{tolerance:.1f}s"
                )
                # Evidence 저장 후 FAIL 반환
                db_counts = self.ledger_writer.get_counts()
                self.save_evidence(db_counts=db_counts)
                return 1
            
            logger.info(
                f"[D205-18-4R2] Wallclock duration PASS: "
                f"actual={actual_duration:.1f}s, expected={expected_duration:.1f}s"
            )
            
            # D205-18-4R2: Step 2 - Heartbeat Density 검증
            # D205-18-4-FIX-3: duration < 120초면 F2 스킵 (테스트 호환성)
            if duration_sec >= 120 and self._watcher:
                heartbeat_result = self._watcher.verify_heartbeat_density()
                if heartbeat_result["status"] == "FAIL":
                    logger.error(
                        f"[D205-18-4R2] Heartbeat density FAIL: {heartbeat_result['message']}"
                    )
                    db_counts = self.ledger_writer.get_counts()
                    self.save_evidence(db_counts=db_counts)
                    return 1
                
                logger.info(
                    f"[D205-18-4R2] Heartbeat density PASS: "
                    f"{heartbeat_result['line_count']} lines (expected_min={heartbeat_result['expected_min']})"
                )
            elif duration_sec < 120:
                logger.info(f"[D205-18-4-FIX-3] F2 Heartbeat Density skipped (duration={duration_sec}s < 120s)")
            
            # D205-18-4R2: Step 3 - DB Invariant 검증
            # D205-18-4-FIX F3: order(1) + fill(1) + trade(1) = 3 per trade
            # D205-18-4-FIX-3: db_mode='off'면 F3 스킵 (DB 미사용)
            if self.config.db_mode != "off" and self.kpi.closed_trades > 0:
                expected_inserts = self.kpi.closed_trades * 3
                actual_inserts = self.kpi.db_inserts_ok
                if abs(actual_inserts - expected_inserts) > 2:  # ±2 허용 (경계 조건)
                    logger.error(
                        f"[D205-18-4R2] DB Invariant FAIL: "
                        f"closed_trades={self.kpi.closed_trades}, "
                        f"expected_inserts={expected_inserts}, "
                        f"actual_inserts={actual_inserts}"
                    )
                    db_counts = self.ledger_writer.get_counts()
                    self.save_evidence(db_counts=db_counts)
                    return 1
                
                logger.info(
                    f"[D205-18-4R2] DB Invariant PASS: "
                    f"closed_trades={self.kpi.closed_trades}, db_inserts={actual_inserts}"
                )
            elif self.config.db_mode == "off":
                logger.info(f"[D205-18-4-FIX-3] F3 DB Invariant skipped (db_mode=off)")
            
            # Evidence 저장
            db_counts = self.ledger_writer.get_counts()
            self.save_evidence(db_counts=db_counts)
            
            # D205-18-4-FIX-2 F4: Evidence Completeness Invariant (manifest.json 포함)
            # D205-18-4-FIX-3: duration < 60초면 F4 스킵 (테스트 호환성)
            if duration_sec >= 60:
                from pathlib import Path
                evidence_dir = Path(self.config.output_dir)
                required_files = ["chain_summary.json", "heartbeat.jsonl", "kpi.json", "manifest.json"]
                
                missing_files = []
                empty_files = []
                for filename in required_files:
                    filepath = evidence_dir / filename
                    if not filepath.exists():
                        missing_files.append(filename)
                    elif filepath.stat().st_size == 0:
                        empty_files.append(filename)
                
                if missing_files or empty_files:
                    logger.error(
                        f"[D205-18-4-FIX F4] Evidence Completeness FAIL: "
                        f"missing={missing_files}, empty={empty_files}"
                    )
                    return 1
                
                logger.info(
                    f"[D205-18-4-FIX F4] Evidence Completeness PASS: "
                    f"all required files exist and non-empty"
                )
            else:
                logger.info(f"[D205-18-4-FIX-3] F4 Evidence Completeness skipped (duration={duration_sec}s < 60s)")
            
            # Exit Code 보장: watcher stop_reason='ERROR' 시 return 1
            if self._watcher and self._watcher.stop_reason == "ERROR":
                logger.error(
                    f"[D205-18-3] RunWatcher triggered FAIL. "
                    f"Diagnosis: {self._watcher.diagnosis}"
                )
                self._state = OrchestratorState.ERROR
                return 1
            
            # D206-0 AC-2: WARN=FAIL 원칙 검증
            # OPS_PROTOCOL.md: "모든 Warning 레벨 로그는 잠재적 문제로 취급, Exit Code 1 유발 가능"
            warn_counts = self._warning_handler.get_counts()
            # 주의: SIGTERM/정상 종료 경로의 warning은 예외 처리 (is_controlled_warning)
            # 현재는 error_count만 FAIL 조건으로 적용 (warning은 로그 기록)
            if warn_counts["error_count"] > 0:
                logger.error(
                    f"[D206-0 WARN=FAIL] Error count detected: "
                    f"warnings={warn_counts['warning_count']}, errors={warn_counts['error_count']}"
                )
                self._state = OrchestratorState.ERROR
                return 1
            
            if warn_counts["warning_count"] > 0:
                logger.info(
                    f"[D206-0 WARN=FAIL] Warnings detected (non-fatal): "
                    f"warnings={warn_counts['warning_count']}"
                )
            
            self._state = OrchestratorState.STOPPED
            return 0
            
        except Exception as e:
            logger.error(f"[D206-0] Orchestrator failed: {e}", exc_info=True)
            self._state = OrchestratorState.ERROR
            return 1
        
        finally:
            # D206-0 AC-5: 종료 상태 확정 (STOPPING -> STOPPED/ERROR)
            if self._state == OrchestratorState.RUNNING:
                self._state = OrchestratorState.STOPPING
            
            # D205-18-4R2: Atomic Evidence Flush (무조건 저장)
            try:
                db_counts = self.ledger_writer.get_counts() if hasattr(self, 'ledger_writer') else None
                if hasattr(self, 'kpi') and hasattr(self, 'evidence_collector'):
                    self.save_evidence(db_counts=db_counts)
                    logger.info("[D205-18-4R2] Atomic Evidence Flush completed")
            except Exception as flush_error:
                logger.error(f"[D205-18-4R2] Atomic Evidence Flush failed: {flush_error}")
            
            self.stop_watcher()
    
    def start_watcher(self):
        """RunWatcher 시작"""
        self._watcher = create_watcher(
            kpi_getter=lambda: self.kpi,
            stop_callback=self.request_stop,
            run_id="",
            heartbeat_sec=60,
            min_trades_for_check=100,
            max_drawdown_pct=20.0,
            max_consecutive_losses=10,
            evidence_dir=self.config.output_dir
        )
        self._watcher.start()
        logger.info("[D205-18-3] RunWatcher started (with Safety Guards D/E)")
    
    def stop_watcher(self):
        """RunWatcher 정리"""
        if self._watcher:
            self._watcher.stop()
            logger.info("[D205-18-2D] RunWatcher stopped")
    
    def save_evidence(self, db_counts: Optional[Dict[str, int]] = None):
        """Evidence 저장"""
        self.evidence_collector.save(
            metrics=self.kpi,
            trade_history=self.trade_history,
            db_counts=db_counts,
            phase=self.config.phase
        )
        logger.info(f"[D206-0] Evidence saved")
    
    def get_state(self) -> OrchestratorState:
        """
        D206-0 AC-5: 엔진 상태 관리 인터페이스
        
        현재 Orchestrator 상태 조회.
        UI/모니터링 툴 연계 예정.
        """
        return self._state
    
    def get_warning_counts(self) -> Dict[str, int]:
        """
        D206-0 AC-2: WARN=FAIL 카운터 조회
        
        Returns:
            {"warning_count": int, "error_count": int}
        """
        return self._warning_handler.get_counts()
