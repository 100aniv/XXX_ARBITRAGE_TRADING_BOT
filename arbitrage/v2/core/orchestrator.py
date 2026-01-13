"""
D205-18-2D: Paper Orchestrator (Engine-Centric, No Runner Callbacks)

Core 컴포넌트만 사용, Runner 의존성 완전 제거.

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


class PaperOrchestrator:
    """
    Paper Execution Orchestrator (Engine-Centric)
    
    D205-18-2D: Runner 콜백 의존 제거, Core 컴포넌트만 사용
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
        
        # D205-18-4-FIX-2 F5: SIGTERM Handler 등록
        self._register_signal_handlers()
    
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
        logger.info(f"[D205-18-2D] Orchestrator starting...")
        
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
            if self._watcher:
                heartbeat_result = self._watcher.verify_heartbeat_density()
                if heartbeat_result["status"] == "FAIL":
                    logger.error(
                        f"[D205-18-4R2] Heartbeat density FAIL: {heartbeat_result['message']}"
                    )
                    # Evidence 저장 후 FAIL 반환
                    db_counts = self.ledger_writer.get_counts()
                    self.save_evidence(db_counts=db_counts)
                    return 1
                
                logger.info(
                    f"[D205-18-4R2] Heartbeat density PASS: "
                    f"{heartbeat_result['line_count']} lines (expected_min={heartbeat_result['expected_min']})"
                )
            
            # D205-18-4R2: Step 3 - DB Invariant 검증
            # D205-18-4-FIX F3: order(1) + fill(1) + trade(1) = 3 per trade
            expected_inserts = self.kpi.closed_trades * 3
            actual_inserts = self.kpi.db_inserts_ok
            if self.kpi.closed_trades > 0:  # 거래가 있을 때만 검증
                if abs(actual_inserts - expected_inserts) > 2:  # ±2 허용 (경계 조건)
                    logger.error(
                        f"[D205-18-4R2] DB Invariant FAIL: "
                        f"closed_trades={self.kpi.closed_trades}, "
                        f"expected_inserts={expected_inserts}, "
                        f"actual_inserts={actual_inserts}"
                    )
                    # Evidence 저장 후 FAIL 반환
                    db_counts = self.ledger_writer.get_counts()
                    self.save_evidence(db_counts=db_counts)
                    return 1
                
                logger.info(
                    f"[D205-18-4R2] DB Invariant PASS: "
                    f"closed_trades={self.kpi.closed_trades}, db_inserts={actual_inserts}"
                )
            
            # Evidence 저장
            db_counts = self.ledger_writer.get_counts()
            self.save_evidence(db_counts=db_counts)
            
            # D205-18-4-FIX-2 F4: Evidence Completeness Invariant (manifest.json 포함)
            from pathlib import Path
            evidence_dir = Path("logs/evidence") / self.run_id
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
            
            # Exit Code 보장: watcher stop_reason='ERROR' 시 return 1
            if self._watcher and self._watcher.stop_reason == "ERROR":
                logger.error(
                    f"[D205-18-3] RunWatcher triggered FAIL. "
                    f"Diagnosis: {self._watcher.diagnosis}"
                )
                return 1
            
            return 0
            
        except Exception as e:
            logger.error(f"[D205-18-2D] Orchestrator failed: {e}", exc_info=True)
            return 1
        
        finally:
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
            run_id=self.run_id,
            heartbeat_sec=60,
            min_trades_for_check=100,
            max_drawdown_pct=20.0,
            max_consecutive_losses=10,
            evidence_dir="logs/evidence"
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
        logger.info(f"[D205-18-2D] Evidence saved")
