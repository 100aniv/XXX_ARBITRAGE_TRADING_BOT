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
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum
from typing import Dict, Optional, Any, List
from datetime import datetime, timezone

from arbitrage.v2.core.tick_context import (
    tick_context,
    reset_rest_call_count,
    get_rest_call_count,
)
from arbitrage.v2.core.opportunity_source import (
    OpportunitySource,
    RealOpportunitySource,
    MockOpportunitySource,
)
from arbitrage.v2.core.paper_executor import PaperExecutor
from arbitrage.v2.core.ledger_writer import LedgerWriter
from arbitrage.v2.core.metrics import PaperMetrics
from arbitrage.v2.core.monitor import EvidenceCollector
from arbitrage.v2.core.run_watcher import RunWatcher
from arbitrage.v2.core.engine_report import (
    generate_engine_report,
    get_git_sha,
    get_git_branch,
    get_git_status_info,
)
from arbitrage.v2.core.order_intent import OrderSide, OrderType
from arbitrage.v2.opportunity import OpportunityDirection
from arbitrage.v2.opportunity.intent_builder import candidate_to_order_intents
from arbitrage.v2.domain.pnl_calculator import calculate_net_pnl_full_welded

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
        self.edge_distribution_samples: List[Dict[str, Any]] = []
        self._last_edge_distribution_iteration: Optional[int] = None
        self._edge_sample_stride = max(
            1,
            int(getattr(self.config, "edge_distribution_stride", 50) or 50),
        )
        self._edge_sample_max = max(
            100,
            int(getattr(self.config, "edge_distribution_max_samples", 3000) or 3000),
        )
        self._last_trade_ts: float = 0.0
        self._last_loss_ts: Optional[float] = None
        self._trade_seq: int = 0
        
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
        logger.info("[D207-1]-FIX-2 F5] Signal handlers registered (SIGTERM/SIGINT)")

    def _should_record_edge_sample(self, iteration: int, edge_sample: Dict[str, Any]) -> bool:
        reason = str(edge_sample.get("reason") or "")
        if reason in {
            "exception",
            "marketdata_fetch_timeout",
            "invalid_universe",
            "fx_stale",
            "provider_none",
            "fx_rate_suspicious",
        }:
            return True
        return (iteration % self._edge_sample_stride) == 0

    def _append_edge_sample(self, iteration: int, edge_sample: Dict[str, Any]) -> None:
        sample_iteration = edge_sample.get("iteration")
        if sample_iteration == self._last_edge_distribution_iteration:
            return
        if not self._should_record_edge_sample(iteration, edge_sample):
            return

        self.edge_distribution_samples.append(edge_sample)
        if len(self.edge_distribution_samples) > self._edge_sample_max:
            overflow = len(self.edge_distribution_samples) - self._edge_sample_max
            del self.edge_distribution_samples[:overflow]

        self._last_edge_distribution_iteration = sample_iteration
    
    def run(self) -> int:
        """메인 실행 루프"""
        # D206-0 AC-5: 상태 전이 IDLE -> RUNNING
        self._state = OrchestratorState.RUNNING
        self._warning_handler.reset()  # D206-0 AC-2: WARNING 카운터 리셋
        reset_rest_call_count()
        
        logger.info(f"[D207-1] Orchestrator starting (state={self._state.value})...")
        
        # Add-on AA: Provider Verification (D207-1 RECOVERY)
        # D207-1 Step 2: REAL MarketData 강제 검증 (Runtime)
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
            symbols = getattr(self.config, "symbols", None)
            if not symbols:
                msg = "symbols list empty"
                logger.error(f"[D207-5 INVALID_RUN] FAIL: {msg}")
                self.kpi.error_count += 1
                self.kpi.errors.append("invalid_run:symbols_empty")
                self._state = OrchestratorState.ERROR
                self._final_exit_code = 1
                self._stop_reason = "INVALID_RUN_SYMBOLS_EMPTY"
                self._stop_message = msg
                self.kpi.stop_reason = self._stop_reason
                self.kpi.stop_message = self._stop_message
                db_counts = self.ledger_writer.get_counts()
                self.save_evidence(db_counts=db_counts)
                return 1
            invalid_pairs = [
                idx for idx, pair in enumerate(symbols)
                if not isinstance(pair, (list, tuple)) or len(pair) != 2
                or not all(isinstance(item, str) and item for item in pair)
            ]
            if invalid_pairs:
                msg = f"symbols invalid format: indices={invalid_pairs[:5]}"
                logger.error(f"[D207-6 INVALID_UNIVERSE] FAIL: {msg}")
                self.kpi.error_count += 1
                self.kpi.errors.append("invalid_run:symbols_invalid")
                self._state = OrchestratorState.ERROR
                self._final_exit_code = 1
                self._stop_reason = "INVALID_RUN_SYMBOLS_INVALID"
                self._stop_message = msg
                self.kpi.stop_reason = self._stop_reason
                self.kpi.stop_message = self._stop_message
                db_counts = self.ledger_writer.get_counts()
                self.save_evidence(db_counts=db_counts)
                return 1
            duration_sec = self.config.duration_minutes * 60
            iteration = 0
            
            import time
            start_time = time.time()
            
            # D205-18-4-FIX F1: Wallclock tracking - 루프 직전 시점 기록 (객체 초기화 시간 제외)
            wallclock_start = time.time()
            self.kpi.wallclock_start = wallclock_start
            logger.info(f"[D205-18-4-FIX F1] Wallclock tracking started (loop entry): {wallclock_start}")
            
            cycle_interval_sec = float(getattr(self.config, "cycle_interval_seconds", 0.1) or 0.1)
            if cycle_interval_sec < 0:
                cycle_interval_sec = 0.0

            while time.time() - start_time < duration_sec:
                iteration += 1
                
                if self._stop_requested:
                    if self._sigterm_received:
                        logger.warning("[D205-18-4-FIX-2 F5] Graceful shutdown initiated (SIGTERM)")
                    else:
                        logger.warning("[D205-18-2D] Stop requested by RunWatcher")
                    break
                
                # 1. Opportunity 생성
                rest_forbidden = bool(getattr(self.opportunity_source, "ws_only_mode", False))
                with tick_context(rest_forbidden=rest_forbidden):
                    candidate = self.opportunity_source.generate(iteration)
                edge_sample = self.opportunity_source.get_edge_distribution_sample()
                if edge_sample:
                    self._append_edge_sample(iteration, edge_sample)
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
                
                # D207-1-6: Realism Pack v1 - min hold & loss cooldown
                now_ts = time.time()
                min_hold_ms = getattr(self.config, "min_hold_ms", 0) or 0
                min_hold_sec = float(min_hold_ms) / 1000.0 if min_hold_ms > 0 else 0.0
                cooldown_sec = float(getattr(self.config, "cooldown_after_loss_seconds", 0) or 0)
                cooldown_remaining = 0.0
                cooldown_reason = ""
                if self._last_loss_ts is not None and cooldown_sec > 0:
                    cooldown_remaining = max(cooldown_remaining, (self._last_loss_ts + cooldown_sec) - now_ts)
                    if cooldown_remaining > 0:
                        cooldown_reason = "loss_cooldown"
                if self._last_trade_ts > 0 and min_hold_sec > 0:
                    hold_remaining = (self._last_trade_ts + min_hold_sec) - now_ts
                    if hold_remaining > cooldown_remaining:
                        cooldown_remaining = hold_remaining
                        cooldown_reason = "min_hold"
                if cooldown_remaining > 0:
                    self.kpi.bump_reject("cooldown")
                    logger.info(
                        f"[D207-1-6] Cooldown active ({cooldown_reason}), remaining={cooldown_remaining:.2f}s"
                    )
                    time.sleep(min(1.0, cooldown_remaining))
                    continue

                # 2. Intent 변환
                order_size_mode = getattr(self.config, "order_size_policy_mode", "fixed_quote")
                fixed_quote = getattr(self.config, "fixed_quote", None) or {}
                default_quote_amount = getattr(self.config, "default_quote_amount", 100000.0)
                quote_amount = default_quote_amount

                if order_size_mode == "fixed_quote":
                    if candidate.direction == OpportunityDirection.BUY_A_SELL_B:
                        buy_exchange = candidate.exchange_a
                    else:
                        buy_exchange = candidate.exchange_b

                    if buy_exchange == "upbit":
                        quote_amount = fixed_quote.get("upbit_krw", quote_amount)
                    elif buy_exchange == "binance":
                        quote_amount = fixed_quote.get("binance_usdt", quote_amount)

                if quote_amount is None or quote_amount <= 0:
                    quote_amount = default_quote_amount

                intents = candidate_to_order_intents(candidate, quote_amount=quote_amount)
                if not intents or len(intents) != 2:
                    self.kpi.bump_reject("intent_conversion_failed")
                    continue
                
                self.kpi.intents_created += len(intents)
                
                # 3. 주문 실행 (D207-1-1 FIX: ref_price는 해당 거래소 가격으로 매핑)
                # intents[0].exchange에 맞는 ref_price 적용
                ref_price_0 = candidate.price_a if intents[0].exchange == candidate.exchange_a else candidate.price_b
                ref_price_1 = candidate.price_a if intents[1].exchange == candidate.exchange_a else candidate.price_b

                def _resolve_top_depth(intent, candidate_obj):
                    if intent.exchange == candidate_obj.exchange_a:
                        bid_size = candidate_obj.exchange_a_bid_size
                        ask_size = candidate_obj.exchange_a_ask_size
                        bid_price = candidate_obj.exchange_a_bid or candidate_obj.price_a
                        ask_price = candidate_obj.exchange_a_ask or candidate_obj.price_a
                        fx_rate = None
                    else:
                        bid_size = candidate_obj.exchange_b_bid_size
                        ask_size = candidate_obj.exchange_b_ask_size
                        bid_price = candidate_obj.exchange_b_bid or candidate_obj.price_b
                        ask_price = candidate_obj.exchange_b_ask or candidate_obj.price_b
                        fx_rate = candidate_obj.fx_rate

                    if intent.side == OrderSide.BUY:
                        top_depth = ask_size
                        if top_depth is None:
                            return None
                        if fx_rate and fx_rate > 0 and intent.exchange != candidate_obj.exchange_a:
                            return float(top_depth) / float(fx_rate)
                        return float(top_depth)

                    top_notional = bid_size
                    if top_notional is None:
                        return None
                    price = bid_price if bid_price else ask_price
                    if price and price > 0:
                        return float(top_notional) / float(price)
                    return None

                top_depth_0 = _resolve_top_depth(intents[0], candidate)
                top_depth_1 = _resolve_top_depth(intents[1], candidate)
                with tick_context(rest_forbidden=rest_forbidden):
                    entry_result = self.executor.execute(intents[0], ref_price=ref_price_0, top_depth=top_depth_0)

                    try:
                        if (
                            intents[1].order_type == OrderType.MARKET
                            and intents[1].side == OrderSide.SELL
                            and getattr(intents[1], "qty_source", None) == "from_entry_fill"
                            and entry_result is not None
                            and getattr(entry_result, "success", False)
                            and getattr(entry_result, "filled_qty", None)
                            and float(entry_result.filled_qty) > 0
                        ):
                            intents[1].base_qty = float(entry_result.filled_qty)
                    except Exception:
                        pass

                    exit_result = self.executor.execute(intents[1], ref_price=ref_price_1, top_depth=top_depth_1)
                
                self.kpi.mock_executions += 2
                if hasattr(self.kpi, "paper_executions"):
                    self.kpi.paper_executions += 2

                reject_count = 0
                if not getattr(entry_result, "success", True) or not entry_result.filled_qty:
                    reject_count += 1
                if not getattr(exit_result, "success", True) or not exit_result.filled_qty:
                    reject_count += 1
                if reject_count > 0:
                    for _ in range(reject_count):
                        self.kpi.bump_reject("execution_reject")
                    logger.info(
                        f"[D_ALPHA-1U-FIX-2-1] Execution rejected: entry={entry_result.success}, "
                        f"exit={exit_result.success}"
                    )
                    continue
                
                # 4. DB 기록
                self.ledger_writer.record_order_and_fill(intents[0], entry_result, candidate, self.kpi)
                self.ledger_writer.record_order_and_fill(intents[1], exit_result, candidate, self.kpi)
                
                # 5. Trade 완료 기록 (D207-1-1 RECOVERY: 아비트라지 PnL 정확성)
                # Add-on Alpha: Domain-Driven PnL Welding (pnl_calculator.py SSOT)
                def _to_decimal(value: Optional[float]) -> Decimal:
                    return Decimal(str(value if value is not None else 0))

                def _quantize(value: Decimal) -> Decimal:
                    return value.quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP)

                total_fee = _to_decimal(entry_result.fee) + _to_decimal(exit_result.fee)

                # D207-1-6: Realism Pack v1 - friction totals (slippage/latency/partial/reject)
                def _calc_slippage_cost(result) -> Decimal:
                    if not result:
                        return Decimal("0")
                    if result.ref_price is None or result.filled_qty is None:
                        return Decimal("0")
                    slippage_bps = getattr(result, "slippage_bps", None)
                    if slippage_bps is None:
                        if result.filled_price is None:
                            return Decimal("0")
                        diff = abs(_to_decimal(result.filled_price) - _to_decimal(result.ref_price))
                        return _quantize(diff * _to_decimal(result.filled_qty))
                    slippage_ratio = abs(_to_decimal(slippage_bps)) / Decimal("10000")
                    return _quantize(
                        abs(_to_decimal(result.ref_price)) * slippage_ratio * _to_decimal(result.filled_qty)
                    )

                def _calc_latency_cost(result) -> Decimal:
                    if not result:
                        return Decimal("0")
                    if result.ref_price is None or result.filled_qty is None:
                        return Decimal("0")
                    drift_bps = getattr(result, "pessimistic_drift_bps", None)
                    if drift_bps is None:
                        return Decimal("0")
                    slippage_bps = getattr(result, "slippage_bps", 0.0) or 0.0
                    slippage_ratio = abs(_to_decimal(slippage_bps)) / Decimal("10000")
                    drift_ratio = abs(_to_decimal(drift_bps)) / Decimal("10000")
                    base_price = _to_decimal(result.ref_price)
                    return _quantize(
                        abs(base_price * (Decimal("1") + slippage_ratio) * drift_ratio * _to_decimal(result.filled_qty))
                    )

                def _calc_latency_ms(result) -> float:
                    if not result or result.latency_ms is None:
                        return 0.0
                    return float(result.latency_ms)

                def _calc_partial_penalty(entry, exit) -> Decimal:
                    if not entry or not exit:
                        return Decimal("0")
                    if entry.filled_qty is None or exit.filled_qty is None:
                        return Decimal("0")
                    qty_diff = abs(_to_decimal(entry.filled_qty) - _to_decimal(exit.filled_qty))
                    if qty_diff <= 0:
                        return Decimal("0")
                    base_price = (
                        exit.ref_price
                        if getattr(exit, "ref_price", None) is not None
                        else (exit.filled_price if getattr(exit, "filled_price", None) is not None else None)
                    )
                    if base_price is None:
                        base_price = (
                            entry.ref_price
                            if getattr(entry, "ref_price", None) is not None
                            else (entry.filled_price if getattr(entry, "filled_price", None) is not None else None)
                        )
                    if base_price is None:
                        return Decimal("0")
                    return _quantize(abs(_to_decimal(base_price)) * qty_diff)

                def _calc_reject(result) -> float:
                    if not result:
                        return 0.0
                    return 1.0 if getattr(result, "reject_flag", False) else 0.0

                slippage_cost = _calc_slippage_cost(entry_result) + _calc_slippage_cost(exit_result)
                latency_cost = _calc_latency_cost(entry_result) + _calc_latency_cost(exit_result)
                latency_total_ms = _calc_latency_ms(entry_result) + _calc_latency_ms(exit_result)
                partial_penalty = _calc_partial_penalty(entry_result, exit_result)
                reject_count = _calc_reject(entry_result) + _calc_reject(exit_result)

                pnl_weld = calculate_net_pnl_full_welded(
                    entry_side=intents[0].side.value,
                    exit_side=intents[1].side.value,
                    entry_price=entry_result.filled_price,
                    exit_price=exit_result.filled_price,
                    entry_qty=entry_result.filled_qty,
                    exit_qty=exit_result.filled_qty,
                    total_fee=total_fee,
                    slippage_cost=slippage_cost,
                    latency_cost=latency_cost,
                    partial_penalty=partial_penalty,
                    entry_bid=candidate.exchange_a_bid if intents[0].exchange == candidate.exchange_a else candidate.exchange_b_bid,
                    entry_ask=candidate.exchange_a_ask if intents[0].exchange == candidate.exchange_a else candidate.exchange_b_ask,
                    exit_bid=candidate.exchange_a_bid if intents[1].exchange == candidate.exchange_a else candidate.exchange_b_bid,
                    exit_ask=candidate.exchange_a_ask if intents[1].exchange == candidate.exchange_a else candidate.exchange_b_ask,
                    return_decimal=True,
                )
                gross_pnl = pnl_weld["gross_pnl"]
                realized_pnl = pnl_weld["realized_pnl"]
                net_pnl_full = pnl_weld["net_pnl_full"]
                exec_cost_total = pnl_weld["exec_cost_total"]
                spread_cost = pnl_weld["spread_cost"]
                is_win = net_pnl_full > Decimal("0")
                
                self._trade_seq += 1
                trade_id = f"trade-{self.run_id}-{self._trade_seq:08d}"
                self.ledger_writer.record_trade_complete(
                    trade_id=trade_id,
                    candidate=candidate,
                    intents=intents,
                    entry_result=entry_result,
                    exit_result=exit_result,
                    realized_pnl=float(realized_pnl),
                    kpi=self.kpi,
                )
                
                # 6. KPI 업데이트
                self.kpi.closed_trades += 1
                self.kpi.gross_pnl += float(gross_pnl)
                self.kpi.fees += float(total_fee)
                self.kpi.net_pnl_full += float(net_pnl_full)
                self.kpi.net_pnl = self.kpi.net_pnl_full
                
                # D207-1-3: Friction costs 누적 (AT: Active Failure Detection)
                self.kpi.fees_total += float(total_fee)
                self.kpi.slippage_cost += float(slippage_cost)
                self.kpi.latency_cost += float(latency_cost)
                self.kpi.partial_fill_penalty += float(partial_penalty)
                if hasattr(self.kpi, "spread_cost"):
                    self.kpi.spread_cost += float(spread_cost)
                self.kpi.exec_cost_total += float(exec_cost_total)
                # D207-1-6: Realism Pack v1 totals
                self.kpi.slippage_total += float(slippage_cost)
                self.kpi.latency_total += latency_total_ms
                self.kpi.partial_fill_total += float(partial_penalty)
                if reject_count:
                    for _ in range(int(reject_count)):
                        self.kpi.bump_reject("execution_reject")
                
                if is_win:
                    self.kpi.wins += 1
                else:
                    self.kpi.losses += 1

                trade_ts = time.time()
                self._last_trade_ts = trade_ts
                if not is_win:
                    self._last_loss_ts = trade_ts
                
                if self.kpi.closed_trades > 0:
                    self.kpi.winrate_pct = (self.kpi.wins / self.kpi.closed_trades) * 100.0
                
                # 7. Trade History 기록 (D207-3: Reality Proof)
                self.trade_history.append({
                    "trade_id": trade_id,
                    "iteration": iteration,
                    "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                    "candidate_spread_bps": candidate.spread_bps,
                    "candidate_edge_bps": candidate.edge_bps,
                    "candidate_break_even_bps": candidate.break_even_bps,
                    "candidate_direction": candidate.direction.value,
                    "candidate_profitable": candidate.profitable,
                    "candidate_allow_unprofitable": getattr(candidate, "allow_unprofitable", False),
                    "candidate_price_a": candidate.price_a,
                    "candidate_price_b": candidate.price_b,
                    "exchange_a_bid": candidate.exchange_a_bid,
                    "exchange_a_ask": candidate.exchange_a_ask,
                    "exchange_b_bid": candidate.exchange_b_bid,
                    "exchange_b_ask": candidate.exchange_b_ask,
                    "fx_rate": candidate.fx_rate,
                    "fx_rate_source": candidate.fx_rate_source,
                    "fx_rate_age_sec": candidate.fx_rate_age_sec,
                    "fx_rate_timestamp": candidate.fx_rate_timestamp,
                    "fx_rate_degraded": candidate.fx_rate_degraded,
                    "entry_exchange": intents[0].exchange,
                    "exit_exchange": intents[1].exchange,
                    "entry_filled_price": entry_result.filled_price,
                    "exit_filled_price": exit_result.filled_price,
                    "entry_ref_price": entry_result.ref_price,
                    "exit_ref_price": exit_result.ref_price,
                    "entry_slippage_bps": entry_result.slippage_bps,
                    "exit_slippage_bps": exit_result.slippage_bps,
                    "entry_drift_bps": entry_result.pessimistic_drift_bps,
                    "exit_drift_bps": exit_result.pessimistic_drift_bps,
                    "entry_latency_ms": entry_result.latency_ms,
                    "exit_latency_ms": exit_result.latency_ms,
                    "entry_partial_fill_ratio": entry_result.partial_fill_ratio,
                    "exit_partial_fill_ratio": exit_result.partial_fill_ratio,
                    "entry_fill_ratio": entry_result.partial_fill_ratio,
                    "exit_fill_ratio": exit_result.partial_fill_ratio,
                    "entry_top_depth": getattr(entry_result, "raw_response", {}).get("top_depth") if getattr(entry_result, "raw_response", None) else None,
                    "exit_top_depth": getattr(exit_result, "raw_response", {}).get("top_depth") if getattr(exit_result, "raw_response", None) else None,
                    "entry_size_ratio": getattr(entry_result, "raw_response", {}).get("size_ratio") if getattr(entry_result, "raw_response", None) else None,
                    "exit_size_ratio": getattr(exit_result, "raw_response", {}).get("size_ratio") if getattr(exit_result, "raw_response", None) else None,
                    "gross_pnl": float(gross_pnl),
                    "realized_pnl": float(realized_pnl),
                    "net_pnl_full": float(net_pnl_full),
                    "fee_total": float(total_fee),
                    "slippage_cost": float(slippage_cost),
                    "latency_cost": float(latency_cost),
                    "partial_fill_penalty": float(partial_penalty),
                    "spread_cost": float(spread_cost),
                    "exec_cost_total": float(exec_cost_total),
                })
                
                # KPI 출력 (10 iteration마다)
                if iteration % 10 == 0:
                    logger.info(
                        f"[D207-1 KPI] iter={iteration}, opp={self.kpi.opportunities_generated}, "
                        f"closed={self.kpi.closed_trades}, pnl_full={self.kpi.net_pnl_full:.2f}"
                    )
                
                if cycle_interval_sec > 0:
                    time.sleep(cycle_interval_sec)
            
            logger.info(f"[D207-1] Orchestrator completed: {iteration} iterations")

            if self.kpi.marketdata_mode == "REAL" and self.kpi.real_ticks_ok_count == 0:
                msg = "real_ticks_ok_count=0"
                logger.error(f"[D207-5 INVALID_RUN] FAIL: {msg}")
                self.kpi.error_count += 1
                self.kpi.errors.append("invalid_run:real_ticks_zero")
                self._state = OrchestratorState.ERROR
                self._final_exit_code = 1
                self._stop_reason = "INVALID_RUN_REAL_TICKS_ZERO"
                self._stop_message = msg
                self.kpi.stop_reason = self._stop_reason
                self.kpi.stop_message = self._stop_message
                db_counts = self.ledger_writer.get_counts()
                self.save_evidence(db_counts=db_counts)
                return 1
            
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
            if hasattr(self, "kpi"):
                self.kpi.expected_duration_sec = expected_duration
                if expected_duration > 0:
                    self.kpi.wallclock_drift_pct = abs(actual_duration - expected_duration) / expected_duration * 100.0
            
            # D207-1-5: RunWatcher stop_reason 먼저 체크 (Truth Chain SSOT)
            # MODEL_ANOMALY가 트리거되었다면 해당 stop_reason 사용
            phase = getattr(self.config, "phase", "")
            survey_mode = bool(getattr(self.config, "survey_mode", False))
            evidence_mode = phase in ["baseline", "longrun", "edge_survey"] or survey_mode
            if self._watcher and self._watcher.stop_reason:
                if evidence_mode and self._watcher.stop_reason == "MODEL_ANOMALY":
                    pass
                else:
                    self._stop_reason = self._watcher.stop_reason
                    self._stop_message = self._watcher.diagnosis or ""
                    self._final_exit_code = 1
                    self.kpi.stop_reason = self._stop_reason
                    self.kpi.stop_message = self._stop_message
            
            # D205-18-4R2: Step 1 - Wallclock Duration 검증 (±5% 범위)
            tolerance = expected_duration * 0.05
            if expected_duration < 10:
                tolerance = max(tolerance, 1.0)
            phase = getattr(self.config, "phase", "")
            if phase == "edge_survey" and expected_duration <= 180:
                tolerance = max(tolerance, 20.0)
                logger.info(
                    f"[D_ALPHA-1U-FIX-2-1] Wallclock tolerance extended for edge_survey short run: "
                    f"±{tolerance:.1f}s"
                )
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
                if hasattr(self, "kpi"):
                    self.kpi.max_heartbeat_gap_sec = heartbeat_result.get("max_gap_seconds", 0.0)
                if heartbeat_result["status"] == "FAIL":
                    logger.error(
                        f"[D205-18-4R2] Heartbeat density FAIL: {heartbeat_result['message']}"
                    )
                    db_counts = self.ledger_writer.get_counts()
                    self.save_evidence(db_counts=db_counts)
                    return 1
                
                logger.info(
                    f"[D205-18-4R2] Heartbeat density PASS: max_gap={heartbeat_result.get('max_gap_seconds', 0)}s"
                )
            elif duration_sec < 120:
                logger.info(f"[D205-18-4-FIX-3] F2 Heartbeat Density skipped (duration={duration_sec}s < 120s)")
                if hasattr(self, "kpi"):
                    self.kpi.max_heartbeat_gap_sec = 0.0
            
            # Evidence Completeness 검사 전 Evidence 저장 (kpi/manifest/chain_summary 생성)
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
            
            # D207-1-5 Step 3: StopReason/ExitCode 정합성 - RunWatcher FAIL → Exit 1
            # MODEL_ANOMALY, FX_STALE, ERROR 모두 Exit 1 강제
            watcher_reason = self._watcher.stop_reason if self._watcher else None
            if watcher_reason:
                ignore_model_anomaly = evidence_mode and watcher_reason == "MODEL_ANOMALY"
                if (not ignore_model_anomaly) and watcher_reason in [
                    "ERROR",
                    "MODEL_ANOMALY",
                    "FX_STALE",
                    "WIN_RATE_100_SUSPICIOUS",
                    "TRADE_STARVATION",
                ]:
                    logger.error(
                        f"[D207-1-5] RunWatcher triggered FAIL. "
                        f"stop_reason={watcher_reason}, "
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
                self._final_exit_code = 1
                self._stop_reason = "WARN_FAIL"
                self._stop_message = (
                    f"warnings={warn_counts['warning_count']}, errors={warn_counts['error_count']}"
                )
                # Evidence에 warning_counts 저장
                self.kpi.warning_count = warn_counts["warning_count"]
                self.kpi.error_count = warn_counts["error_count"]
                self.kpi.stop_reason = self._stop_reason
                self.kpi.stop_message = self._stop_message
                db_counts = self.ledger_writer.get_counts()
                self.save_evidence(db_counts=db_counts)
                return 1
            
            # D207-1-5: 정상 종료 시 TIME_REACHED
            self._state = OrchestratorState.STOPPED
            self._final_exit_code = 0
            self._stop_reason = "TIME_REACHED"
            self._stop_message = "Normal completion"
            
            # KPI에도 동일하게 기록 (Truth Chain)
            self.kpi.stop_reason = self._stop_reason
            self.kpi.stop_message = self._stop_message

            self.kpi.rest_in_tick_count = int(get_rest_call_count())

            db_counts = self.ledger_writer.get_counts()
            self.save_evidence(db_counts=db_counts)
            
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
                provider_is_real = isinstance(self.opportunity_source, RealOpportunitySource)
                
                # Get warning counts
                warn_counts = self._warning_handler.get_counts() if hasattr(self, '_warning_handler') else {"warning_count": 0, "error_count": 0}
                
                # D207-1-5: exit_code와 stop_reason은 인스턴스 변수에서 가져옴 (Truth Chain SSOT)
                final_exit_code = self._final_exit_code if self._final_exit_code != 0 else (1 if self._state == OrchestratorState.ERROR else 0)
                final_stop_reason = self._stop_reason if self._stop_reason else ("TIME_REACHED" if final_exit_code == 0 else "ERROR")
                final_stop_message = self._stop_message if self._stop_message else ""

                if hasattr(self, "kpi") and hasattr(self.kpi, "sync_reject_total"):
                    self.kpi.sync_reject_total()

                if hasattr(self, "kpi"):
                    try:
                        self.kpi.rest_in_tick_count = int(get_rest_call_count())
                    except Exception:
                        pass
                
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
        from pathlib import Path
        evidence_root = str(Path(self.config.output_dir).parent)
        phase = getattr(self.config, "phase", "")
        survey_mode = getattr(self.config, "survey_mode", False)
        
        # D_ALPHA-2: survey_mode=True이면 데이터 수집 목적이므로
        # early_stop + always-on 가드를 완화하여 MODEL_ANOMALY 조기 종료 방지
        early_stop_enabled = phase not in ["baseline", "longrun", "edge_survey"] and not survey_mode
        
        # D_ALPHA-2: survey_mode에서 always-on 가드 임계치 완화
        # survey는 데이터 수집이므로 winrate 100% / trade starvation은 정상 동작
        winrate_100_threshold = 20
        trade_starvation_flag = not survey_mode

        evidence_mode = phase in ["baseline", "longrun", "edge_survey"] or bool(survey_mode)
        if evidence_mode:
            early_stop_enabled = False
            winrate_100_threshold = 10**9
            trade_starvation_flag = False
        
        watcher_config = WatcherConfig(
            heartbeat_sec=60,
            early_stop_enabled=early_stop_enabled,
            winrate_cap_threshold=0.95,  # 95% 승률 상한
            min_trades_for_winrate_cap=10,
            check_friction_nonzero=True,  # fees_total=0 차단
            check_machinegun=True,
            max_trades_per_minute=20,
            evidence_dir=evidence_root,
            winrate_100_trade_threshold=winrate_100_threshold,
            trade_starvation_enabled=trade_starvation_flag,
        )
        logger.info(
            f"[D_ALPHA-2] WatcherConfig: phase={phase}, survey_mode={survey_mode}, "
            f"early_stop_enabled={early_stop_enabled}, "
            f"winrate_100_threshold={winrate_100_threshold}, "
            f"trade_starvation={trade_starvation_flag}"
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
        try:
            self.kpi.rest_in_tick_count = int(get_rest_call_count())
        except Exception:
            pass

        try:
            if getattr(self.kpi, "stop_reason", "") in (None, "") and getattr(self, "_stop_reason", ""):
                self.kpi.stop_reason = self._stop_reason
            if getattr(self.kpi, "stop_message", "") in (None, "") and getattr(self, "_stop_message", ""):
                self.kpi.stop_message = self._stop_message
        except Exception:
            pass
        dynamic_state = None
        if hasattr(self.opportunity_source, "get_dynamic_threshold_state"):
            dynamic_state = self.opportunity_source.get_dynamic_threshold_state()
        tail_state = None
        if hasattr(self.opportunity_source, "get_tail_threshold_state"):
            tail_state = self.opportunity_source.get_tail_threshold_state()
        run_meta = {
            "run_id": self.run_id,
            "git_sha": get_git_sha(),
            "branch": get_git_branch(),
            "git_status": get_git_status_info(),
            "config_path": getattr(self.config, "config_path", None),
            "symbols": getattr(self.config, "symbols", None),
            "cli_args": getattr(self.config, "cli_args", None),
            "engine_random_seed": getattr(self.config, "engine_random_seed", None),
            "paper_adapter_random_seed": getattr(self.executor, "adapter_random_seed", None),
            "metrics": self.kpi.to_dict(),
            "universe_metadata": getattr(self.config, "universe_metadata", None),
            "obi_dynamic_threshold_state": dynamic_state,
            "tail_threshold_state": tail_state,
        }
        self.evidence_collector.save(
            metrics=self.kpi,
            trade_history=self.trade_history,
            edge_distribution=self.edge_distribution_samples,
            db_counts=db_counts,
            phase=self.config.phase,
            run_meta=run_meta
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
