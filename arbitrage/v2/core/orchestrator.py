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
from arbitrage.v2.core.run_watcher import RunWatcher
from arbitrage.v2.core.engine_report import generate_engine_report
from arbitrage.v2.core.order_intent import OrderSide
from arbitrage.v2.opportunity.intent_builder import candidate_to_order_intents
from arbitrage.v2.domain.pnl_calculator import calculate_pnl_summary

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
        
        # D207-1-5: StopReason Single Truth Chain (SSOT)
        self._final_exit_code = 0
        self._stop_reason = ""
        self._stop_message = ""
        
        # D206-0 AC-2: WARN=FAIL Handler
        self._warning_handler = WarningCounterHandler()
        logging.getLogger().addHandler(self._warning_handler)
        
        # D205-18-4-FIX-2 F5: SIGTERM Handler 등록
        self._register_signal_handlers()
        
        logger.info("[D206-0] Orchestrator initialized with OPS Protocol embedded")
    
    def request_stop(self):
        """RunWatcher 중단 요청"""
        logger.warning("[D207-1] Stop requested by RunWatcher")
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
        logger.error("[D207-1]-FIX-2 F5] Signal handlers registered (SIGTERM/SIGINT)")
    
    def run(self) -> int:
        """메인 실행 루프"""
        # D206-0 AC-5: 상태 전이 IDLE -> RUNNING
        self._state = OrchestratorState.RUNNING
        self._warning_handler.reset()  # D206-0 AC-2: WARNING 카운터 리셋
        
        logger.info(f"[D207-1] Orchestrator starting (state={self._state.value})...")
        
        # Add-on AA: Provider Verification (D207-1 RECOVERY)
        # D207-1 Step 2: REAL MarketData 강제 검증 (Runtime)
        from arbitrage.v2.core.opportunity_source import RealOpportunitySource, MockOpportunitySource
        provider_class_name = self.opportunity_source.__class__.__name__
        is_real = isinstance(self.opportunity_source, RealOpportunitySource)
        is_mock = isinstance(self.opportunity_source, MockOpportunitySource)
        
        logger.info(f"[Provider Verification] Class: {provider_class_name}, is_real={is_real}, is_mock={is_mock}")
        
        # D207-1 Step 2: baseline/longrun phase에서 Mock 발견 시 즉시 Exit 1
        if hasattr(self.config, 'phase') and self.config.phase in ["baseline", "longrun"]:
            if is_mock:
                logger.error(f"[D207-1 REAL GUARD] FAIL: phase={self.config.phase} but provider is MockOpportunitySource")
                logger.error(f"[D207-1 REAL GUARD] Expected: RealOpportunitySource, Got: {provider_class_name}")
                logger.error(f"[D207-1 REAL GUARD] Fix: Ensure --use-real-data flag is passed and RuntimeFactory uses RealOpportunitySource")
                self._state = OrchestratorState.ERROR
                return 1  # 즉시 Exit 1
        
        # Record provider type in KPI (for engine_report)
        if hasattr(self.kpi, 'provider_class_name'):
            self.kpi.provider_class_name = provider_class_name
        if hasattr(self.kpi, 'provider_is_real'):
            self.kpi.provider_is_real = is_real
        
        # marketdata_mode 라벨 강제 정합성 (REAL/MOCK)
        self.kpi.marketdata_mode = "REAL" if is_real else "MOCK"
        self.kpi.upbit_marketdata_ok = is_real
        self.kpi.binance_marketdata_ok = is_real
        logger.info(f"[D207-1] marketdata_mode set to: {self.kpi.marketdata_mode}")
        
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
                
                # 3. 주문 실행 (D207-1-1 FIX: ref_price는 해당 거래소 가격으로 매핑)
                # intents[0].exchange에 맞는 ref_price 적용
                ref_price_0 = candidate.price_a if intents[0].exchange == candidate.exchange_a else candidate.price_b
                ref_price_1 = candidate.price_a if intents[1].exchange == candidate.exchange_a else candidate.price_b
                entry_result = self.executor.execute(intents[0], ref_price=ref_price_0)
                exit_result = self.executor.execute(intents[1], ref_price=ref_price_1)
                
                self.kpi.mock_executions += 2
                
                # 4. DB 기록
                self.ledger_writer.record_order_and_fill(intents[0], entry_result, candidate, self.kpi)
                self.ledger_writer.record_order_and_fill(intents[1], exit_result, candidate, self.kpi)
                
                # 5. Trade 완료 기록 (D207-1-1 RECOVERY: 아비트라지 PnL 정확성)
                # Add-on Alpha: Domain-Driven PnL (pnl_calculator.py SSOT)
                total_fee = entry_result.fee + exit_result.fee
                
                # PnL 계산: pnl_calculator.py로 일원화 (중복 방지)
                gross_pnl, realized_pnl, is_win = calculate_pnl_summary(
                    entry_side=intents[0].side.value,
                    exit_side=intents[1].side.value,
                    entry_price=entry_result.filled_price,
                    exit_price=exit_result.filled_price,
                    quantity=entry_result.filled_qty,
                    total_fee=total_fee
                )
                
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
                self.kpi.gross_pnl += gross_pnl
                self.kpi.fees += total_fee
                self.kpi.net_pnl = self.kpi.gross_pnl - self.kpi.fees
                
                # D207-1-3: Friction costs 누적 (AT: Active Failure Detection)
                self.kpi.fees_total += total_fee
                # slippage_cost: MockAdapter는 항상 0, RealAdapter만 계산
                # latency_cost: 현재 미구현 (D208에서 추가 예정)
                # partial_fill_penalty: 현재 미구현 (D208에서 추가 예정)
                
                if is_win:
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
                    logger.info(f"[D207-1 KPI] iter={iteration}, opp={self.kpi.opportunities_generated}, closed={self.kpi.closed_trades}, pnl={self.kpi.net_pnl:.2f}")
                
                time.sleep(0.1)
            
            logger.info(f"[D207-1] Orchestrator completed: {iteration} iterations")
            
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
            
            # D207-1-5: RunWatcher stop_reason 먼저 체크 (Truth Chain SSOT)
            # MODEL_ANOMALY가 트리거되었다면 해당 stop_reason 사용
            if self._watcher and self._watcher.stop_reason:
                self._stop_reason = self._watcher.stop_reason
                self._stop_message = self._watcher.diagnosis or ""
                self._final_exit_code = 1
                self.kpi.stop_reason = self._stop_reason
                self.kpi.stop_message = self._stop_message
            
            # D205-18-4R2: Step 1 - Wallclock Duration 검증 (±5% 범위)
            tolerance = expected_duration * 0.05
            if abs(actual_duration - expected_duration) > tolerance:
                logger.error(
                    f"[D205-18-4R2] Wallclock duration FAIL: "
                    f"actual={actual_duration:.1f}s, expected={expected_duration:.1f}s, "
                    f"tolerance=±{tolerance:.1f}s"
                )
                # D207-1-5: stop_reason이 아직 설정되지 않았다면 WALLCLOCK_FAIL 설정
                if not self._stop_reason:
                    self._stop_reason = "WALLCLOCK_FAIL"
                    self._stop_message = f"actual={actual_duration:.1f}s, expected={expected_duration:.1f}s"
                    self._final_exit_code = 1
                    self.kpi.stop_reason = self._stop_reason
                    self.kpi.stop_message = self._stop_message
                
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
                    f"[D205-18-4R2] Heartbeat density PASS: max_gap={heartbeat_result.get('max_gap_sec', 0)}s"
                )
            elif duration_sec < 120:
                logger.info(f"[D205-18-4-FIX-3] F2 Heartbeat Density skipped (duration={duration_sec}s < 120s)")
            
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
            
            # D207-1-5 Step 3: StopReason/ExitCode 정합성 - RunWatcher FAIL → Exit 1
            # MODEL_ANOMALY, FX_STALE, ERROR 모두 Exit 1 강제
            if self._watcher and self._watcher.stop_reason in ["ERROR", "MODEL_ANOMALY", "FX_STALE"]:
                logger.error(
                    f"[D207-1-5] RunWatcher triggered FAIL. "
                    f"stop_reason={self._watcher.stop_reason}, "
                    f"Diagnosis: {self._watcher.diagnosis}"
                )
                self._state = OrchestratorState.ERROR
                
                # Evidence 저장 (finally 블록 전에)
                db_counts = self.ledger_writer.get_counts()
                self.save_evidence(db_counts=db_counts)
                
                return 1
            
            # D206-0 FIX: WARN=FAIL 원칙 강제 (WARNING도 FAIL)
            # OPS_PROTOCOL.md: "모든 Warning 레벨 로그는 잠재적 문제로 취급, Exit Code 1 유발"
            # 허용 WARNING 목록은 config/v2/config.yml의 ops.warn_allowlist_patterns로 관리 (향후)
            warn_counts = self._warning_handler.get_counts()
            
            if warn_counts["error_count"] > 0 or warn_counts["warning_count"] > 0:
                logger.error(
                    f"[D206-0 WARN=FAIL] FAIL: warnings={warn_counts['warning_count']}, "
                    f"errors={warn_counts['error_count']}"
                )
                self._state = OrchestratorState.ERROR
                # Evidence에 warning_counts 저장
                self.kpi.warning_count = warn_counts["warning_count"]
                self.kpi.error_count = warn_counts["error_count"]
                return 1
            
            # D207-1-5: 정상 종료 시 TIME_REACHED
            self._state = OrchestratorState.STOPPED
            self._final_exit_code = 0
            self._stop_reason = "TIME_REACHED"
            self._stop_message = "Normal completion"
            
            # KPI에도 동일하게 기록 (Truth Chain)
            self.kpi.stop_reason = self._stop_reason
            self.kpi.stop_message = self._stop_message
            
            return 0
            
        except Exception as e:
            logger.error(f"[D206-0] Orchestrator failed: {e}", exc_info=True)
            self._state = OrchestratorState.ERROR
            return 1
        
        finally:
            # D206-0 AC-5: 종료 상태 확정 (STOPPING -> STOPPED/ERROR)
            if self._state == OrchestratorState.RUNNING:
                self._state = OrchestratorState.STOPPING
            
            # D205-18-4R2 + D206-0: Atomic Evidence Flush + Engine Report
            try:
                db_counts = self.ledger_writer.get_counts() if hasattr(self, 'ledger_writer') else None
                
                # Add-on AA: Provider Verification - pass to engine_report
                provider_class_name = self.opportunity_source.__class__.__name__
                from arbitrage.v2.core.opportunity_source import RealOpportunitySource
                provider_is_real = isinstance(self.opportunity_source, RealOpportunitySource)
                
                # Get warning counts
                warn_counts = self._warning_handler.get_counts() if hasattr(self, '_warning_handler') else {"warning_count": 0, "error_count": 0}
                
                # D207-1-5: exit_code와 stop_reason은 인스턴스 변수에서 가져옴 (Truth Chain SSOT)
                final_exit_code = self._final_exit_code if self._final_exit_code != 0 else (1 if self._state == OrchestratorState.ERROR else 0)
                final_stop_reason = self._stop_reason if self._stop_reason else ("TIME_REACHED" if final_exit_code == 0 else "ERROR")
                final_stop_message = self._stop_message if self._stop_message else ""
                
                # Wallclock duration (fallback if not defined)
                wallclock_duration = 0.0
                expected_duration = self.config.duration_minutes * 60 if hasattr(self.config, 'duration_minutes') else 0.0
                if hasattr(self, 'kpi') and hasattr(self.kpi, 'wallclock_start'):
                    wallclock_duration = time.time() - self.kpi.wallclock_start
                
                from arbitrage.v2.core.engine_report import generate_engine_report, save_engine_report_atomic
                
                # Generate report with stop_reason (D207-1-5 Truth Chain)
                report = generate_engine_report(
                    run_id=self.run_id,
                    config=self.config,
                    kpi=self.kpi,
                    warning_counts=warn_counts,
                    wallclock_duration=wallclock_duration,
                    expected_duration=expected_duration,
                    db_counts=db_counts,
                    exit_code=final_exit_code,
                    stop_reason=final_stop_reason,
                    stop_message=final_stop_message
                )
                
                # Save with atomic flush
                save_engine_report_atomic(report, self.config.output_dir)
                logger.info("[D206-0] Standard Engine Report saved (Artifact-First)")
                
                # D207-1-1: watch_summary.json 생성 (OPS_PROTOCOL 필수 파일)
                import json
                from datetime import datetime, timezone
                from pathlib import Path
                
                watch_summary = {
                    "planned_total_hours": self.config.duration_minutes / 60.0 if hasattr(self.config, 'duration_minutes') else 0.0,
                    "started_at_utc": datetime.fromtimestamp(self.kpi.wallclock_start, tz=timezone.utc).isoformat() if hasattr(self.kpi, 'wallclock_start') else None,
                    "ended_at_utc": datetime.now(timezone.utc).isoformat(),
                    "monotonic_elapsed_sec": wallclock_duration,
                    "completeness_ratio": 1.0 if final_exit_code == 0 else (wallclock_duration / expected_duration if expected_duration > 0 else 0.0),
                    "stop_reason": "TIME_REACHED" if final_exit_code == 0 else (self._watcher.stop_reason if self._watcher and self._watcher.stop_reason else "ERROR")
                }
                
                watch_summary_path = Path(self.config.output_dir) / "watch_summary.json"
                with open(watch_summary_path, "w", encoding="utf-8") as f:
                    json.dump(watch_summary, f, indent=2)
                    f.flush()
                    import os
                    os.fsync(f.fileno())
                
                logger.info(f"[D207-1-1] watch_summary.json saved: {watch_summary_path}")
                
            except Exception as flush_error:
                logger.error(f"[D206-0] Atomic Evidence/Report Flush failed: {flush_error}")
            
            self.stop_watcher()
    
    def start_watcher(self):
        """RunWatcher 시작 (D207-1-3: MODEL_ANOMALY Guards)"""
        if self._watcher:
            logger.warning("[Orchestrator] Watcher already running")
            return
        
        from arbitrage.v2.core.run_watcher import RunWatcher, WatcherConfig
        
        # D207-1-3: WatcherConfig with MODEL_ANOMALY Guards (winrate cap, friction check)
        watcher_config = WatcherConfig(
            heartbeat_sec=60,
            winrate_cap_threshold=0.95,  # 95% 승률 상한
            min_trades_for_winrate_cap=10,
            check_friction_nonzero=True,  # fees_total=0 차단
            check_machinegun=True,
            max_trades_per_minute=20,
            evidence_dir=self.config.output_dir,
        )
        
        self._watcher = RunWatcher(
            config=watcher_config,
            kpi_getter=lambda: self.kpi,
            stop_callback=self.request_stop,
            run_id=self.run_id
        )
        self._watcher.start()
        logger.info("[D207-1-3] RunWatcher started (winrate_cap=95%, friction_check=ON, machinegun_guard=ON)")
    
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
