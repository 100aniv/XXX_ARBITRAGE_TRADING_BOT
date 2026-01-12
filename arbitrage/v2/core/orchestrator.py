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
        self._watcher = None
        self.trade_history = []
    
    def request_stop(self):
        """RunWatcher 중단 요청"""
        logger.warning("[D205-18-2D] Stop requested by RunWatcher")
        self._stop_requested = True
    
    def run(self) -> int:
        """메인 실행 루프 (Wall-Clock 기반 Duration 측정)"""
        logger.info(f"[D205-18-2D] Orchestrator starting (duration={self.config.duration_minutes}m)...")
        
        # RunWatcher 시작
        self.start_watcher()
        
        try:
            duration_sec = self.config.duration_minutes * 60
            iteration = 0
            
            import time
            start_time = time.time()
            self.kpi.start_time = start_time  # KPI에 시작 시간 기록
            
            while time.time() - start_time < duration_sec:
                iteration += 1
                
                if self._stop_requested:
                    logger.warning("[D205-18-2D] Stop requested")
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
            
            # Wall-Clock Duration 측정
            actual_duration_sec = time.time() - start_time
            self.kpi.actual_duration_sec = actual_duration_sec
            
            logger.info(f"[D205-18-2D] Orchestrator completed: {iteration} iterations, {actual_duration_sec:.2f}s wall-clock")
            
            # Duration 검증 (설정값 vs 실제값)
            self._verify_wallclock_duration(duration_sec, actual_duration_sec)
            
            # Evidence 저장
            db_counts = self.ledger_writer.get_counts()
            self.save_evidence(db_counts=db_counts)
            
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
    
    def _verify_wallclock_duration(self, expected_sec: int, actual_sec: float) -> None:
        """
        Wall-Clock Duration 검증
        
        Args:
            expected_sec: 설정된 duration (초)
            actual_sec: 실제 실행 시간 (초)
        """
        tolerance_pct = 5.0  # ±5% 허용
        tolerance_sec = expected_sec * (tolerance_pct / 100.0)
        
        logger.info(
            f"[D205-18-4R] Duration Verification: "
            f"expected={expected_sec}s, actual={actual_sec:.2f}s, "
            f"tolerance=±{tolerance_sec:.2f}s ({tolerance_pct}%)"
        )
        
        if actual_sec < (expected_sec - tolerance_sec):
            logger.warning(
                f"[D205-18-4R] WARN: Actual duration {actual_sec:.2f}s < "
                f"expected {expected_sec}s (tolerance: {tolerance_sec:.2f}s). "
                f"Execution may have terminated early."
            )
        elif actual_sec > (expected_sec + tolerance_sec):
            logger.warning(
                f"[D205-18-4R] WARN: Actual duration {actual_sec:.2f}s > "
                f"expected {expected_sec}s (tolerance: {tolerance_sec:.2f}s). "
                f"Execution may have run longer than expected."
            )
        else:
            logger.info(f"[D205-18-4R] PASS: Duration within tolerance")
    
    def save_evidence(self, db_counts: Optional[Dict[str, int]] = None):
        """Evidence 저장"""
        self.evidence_collector.save(
            metrics=self.kpi,
            trade_history=self.trade_history,
            db_counts=db_counts,
            phase=self.config.phase
        )
        logger.info(f"[D205-18-2D] Evidence saved")
