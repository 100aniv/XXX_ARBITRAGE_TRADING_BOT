"""
D205-18-2C: Paper Orchestrator (Engine-Centric)

PaperRunner에서 분리된 orchestration 로직.
Runner는 이 Orchestrator를 호출만 함.

Purpose:
- Opportunity 생성 로직
- Intent 변환 및 실행
- KPI/Evidence 저장
- RunWatcher 통합

Author: arbitrage-lite V2
Date: 2026-01-11
"""

import logging
from typing import Dict, Any, Optional, Callable
from pathlib import Path

from arbitrage.v2.core.metrics import PaperMetrics
from arbitrage.v2.core.monitor import EvidenceCollector
from arbitrage.v2.core.run_watcher import create_watcher
from arbitrage.v2.opportunity import OpportunityCandidate

logger = logging.getLogger(__name__)


class PaperOrchestrator:
    """
    Paper Execution Orchestrator (Engine-Centric)
    
    D205-18-2C: PaperRunner의 orchestration 로직을 분리
    - Opportunity 생성 콜백
    - Intent 처리 콜백
    - RunWatcher 통합
    - Evidence 저장
    """
    
    def __init__(
        self,
        metrics: PaperMetrics,
        evidence_collector: EvidenceCollector,
        opportunity_generator: Callable[[int], Optional[OpportunityCandidate]],
        intent_converter: Callable[[OpportunityCandidate, int], list],
        trade_processor: Callable[[OpportunityCandidate, list], int],
        admin_control: Optional[Any] = None
    ):
        """
        Args:
            metrics: PaperMetrics 인스턴스
            evidence_collector: EvidenceCollector 인스턴스
            opportunity_generator: Opportunity 생성 콜백 (iteration -> candidate)
            intent_converter: Intent 변환 콜백 (candidate, iteration -> intents)
            trade_processor: Trade 처리 콜백 (candidate, intents -> exit_code)
            admin_control: AdminControl 인스턴스 (optional)
        """
        self.metrics = metrics
        self.evidence_collector = evidence_collector
        self.opportunity_generator = opportunity_generator
        self.intent_converter = intent_converter
        self.trade_processor = trade_processor
        self.admin_control = admin_control
        
        self._stop_requested = False
        self._watcher = None
    
    def request_stop(self):
        """RunWatcher에서 호출되는 중단 요청"""
        logger.warning("[Orchestrator] Stop requested by RunWatcher")
        self._stop_requested = True
    
    def create_fetch_callback(self):
        """
        Engine.run()에 전달할 fetch_tick_data 콜백 생성
        
        Returns:
            Callable[[int], Optional[OpportunityCandidate]]
        """
        def fetch_tick_data(iteration):
            """Opportunity 생성 콜백"""
            candidate = self.opportunity_generator(iteration)
            
            if not candidate:
                self.metrics.bump_reject("candidate_none")
                return None
            
            self.metrics.opportunities_generated += 1
            return candidate
        
        return fetch_tick_data
    
    def create_process_callback(self):
        """
        Engine.run()에 전달할 process_tick 콜백 생성
        
        Returns:
            Callable[[int, list, list], None]
        """
        def process_tick(iteration, opportunities, intents):
            """Intent 변환 및 Trade 처리"""
            # RunWatcher FAIL-fast
            if self._stop_requested:
                logger.warning("[Orchestrator] Stop requested, skipping tick")
                raise RuntimeError("RunWatcher triggered stop")
            
            # Opportunity 검증
            if not opportunities or opportunities[0] is None:
                return
            
            candidate = opportunities[0]
            
            # AdminControl 체크
            if self.admin_control:
                if not self.admin_control.should_process_tick():
                    self.metrics.bump_reject("admin_paused")
                    return
                
                if self.admin_control.is_symbol_blacklisted(candidate.symbol):
                    self.metrics.bump_reject("symbol_blacklisted")
                    return
            
            # Intent 변환
            intents_local = self.intent_converter(candidate, iteration)
            intents.extend(intents_local)
            self.metrics.intents_created += len(intents_local)
            
            # Trade 처리
            exit_code = self.trade_processor(candidate, intents_local)
            if exit_code == 1:
                logger.error("[Orchestrator] Fake-Optimism detected")
                raise RuntimeError("Fake-Optimism detected")
            
            # KPI 출력 (10 iteration마다)
            if iteration % 10 == 0:
                logger.info(f"[Orchestrator KPI] {self.metrics.to_dict()}")
        
        return process_tick
    
    def start_watcher(self):
        """RunWatcher 시작"""
        self._watcher = create_watcher(
            kpi_getter=lambda: self.metrics,
            stop_callback=self.request_stop,
            heartbeat_sec=60,
            min_trades_for_check=100
        )
        self._watcher.start()
        logger.info("[Orchestrator] RunWatcher started (60s heartbeat)")
    
    def stop_watcher(self):
        """RunWatcher 정리"""
        if self._watcher:
            self._watcher.stop()
            logger.info("[Orchestrator] RunWatcher stopped")
    
    def save_evidence(self, trade_history: list, db_counts: Optional[Dict[str, int]] = None, phase: str = "unknown"):
        """
        Evidence 저장
        
        Args:
            trade_history: Trade 기록 리스트
            db_counts: DB row counts
            phase: 실행 phase
        """
        self.evidence_collector.save(
            metrics=self.metrics,
            trade_history=trade_history,
            db_counts=db_counts,
            phase=phase
        )
        logger.info(f"[Orchestrator] Evidence saved: {self.evidence_collector.output_dir}")
