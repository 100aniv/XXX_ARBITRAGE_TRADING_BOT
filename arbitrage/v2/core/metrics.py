"""
Paper Metrics Collector (Engine-Centric)

PaperRunner에서 KPI 집계 로직 분리.
Live Runner에서도 재사용 가능.

Purpose:
- Opportunities, trades, orders 카운팅
- Reject reasons 추적
- PnL 계산
- MarketData/Redis 상태 추적
- KPI dict 생성

Author: arbitrage-lite V2
Date: 2026-01-11
"""

import time
import psutil
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from datetime import datetime


@dataclass
class PaperMetrics:
    """
    Paper 실행 메트릭 수집기
    
    EXEC: PaperRunner에서 분리
    - Runner는 이 클래스 인스턴스만 참조
    - 모든 집계 로직은 여기에 집중
    
    PERF: Wallclock duration tracking 추가
    - start_time: 초기 생성 시간 (레거시)
    - wallclock_start: 실제 실행 시작 시간 (wall-clock 기준)
    """
    start_time: float = field(default_factory=time.time)
    wallclock_start: float = field(default_factory=time.time)  # PERF: Wall-clock 기준
    expected_duration_sec: float = 0.0
    wallclock_drift_pct: float = 0.0
    max_heartbeat_gap_sec: float = 0.0
    opportunities_generated: int = 0
    intents_created: int = 0
    mock_executions: int = 0
    paper_executions: int = 0
    db_inserts_ok: int = 0
    db_inserts_failed: int = 0
    error_count: int = 0
    errors: List[str] = field(default_factory=list)
    db_last_error: str = ""
    
    # EXEC: WARN=FAIL 카운터 (Evidence 저장용)
    warning_count: int = 0  # WarningCounterHandler에서 수집
    memory_mb: float = 0.0
    cpu_pct: float = 0.0

    # PERF: Per-tick latency samples (ms)
    tick_elapsed_ms_samples: List[float] = field(default_factory=list)  # deprecated alias -> interval
    tick_compute_ms_samples: List[float] = field(default_factory=list)
    tick_interval_ms_samples: List[float] = field(default_factory=list)
    tick_sleep_ms_samples: List[float] = field(default_factory=list)
    tick_ticker_fetch_ms_samples: List[float] = field(default_factory=list)
    tick_orderbook_fetch_ms_samples: List[float] = field(default_factory=list)
    tick_decision_ms_samples: List[float] = field(default_factory=list)
    tick_io_ms_samples: List[float] = field(default_factory=list)
    md_upbit_ms_samples: List[float] = field(default_factory=list)
    md_binance_ms_samples: List[float] = field(default_factory=list)
    md_total_ms_samples: List[float] = field(default_factory=list)
    compute_decision_ms_samples: List[float] = field(default_factory=list)
    rate_limiter_wait_ms_samples: List[float] = field(default_factory=list)
    
    # EXEC: PnL 필드
    closed_trades: int = 0
    gross_pnl: float = 0.0
    net_pnl: float = 0.0
    net_pnl_full: float = 0.0
    fees: float = 0.0
    wins: int = 0
    losses: int = 0
    winrate_pct: float = 0.0
    
    # EXEC: Real MarketData 증거
    marketdata_mode: str = "MOCK"  # MOCK or REAL
    upbit_marketdata_ok: bool = False
    binance_marketdata_ok: bool = False
    real_ticks_ok_count: int = 0
    real_ticks_fail_count: int = 0
    
    # EXEC: Redis 지표
    redis_ok: bool = False
    ratelimit_hits: int = 0
    dedup_hits: int = 0
    rest_in_tick_count: int = 0
    
    # EXEC: Decision Trace (reject reason 카운트)
    reject_reasons: Dict[str, int] = field(default_factory=lambda: {
        "profitable_false": 0,
        "direction_none": 0,
        "edge_bps_below_zero": 0,
        "units_mismatch": 0,
        "sanity_guard": 0,
        "other": 0,
        "candidate_none": 0,
        "intent_conversion_failed": 0,
        "symbol_blacklisted": 0,
        "admin_paused": 0,  # EXEC: AdminControl reject
        "cooldown": 0,
        "fx_stale": 0,
        "exit_candidate_none": 0,
        "execution_reject": 0,
        "tail_threshold_drop": 0,
    })
    
    # EXEC: FX Rate Info (Economic Truth - Real-time FX)
    fx_rate: float = 0.0
    fx_rate_source: str = "unknown"
    fx_rate_age_sec: float = 0.0
    fx_rate_timestamp: str = ""
    fx_rate_degraded: bool = False
    
    # EXEC: Friction Costs (Economic Truth - Reality Model)
    fees_total: float = 0.0
    slippage_cost: float = 0.0
    latency_cost: float = 0.0
    partial_fill_penalty: float = 0.0
    spread_cost: float = 0.0
    exec_cost_total: float = 0.0
    # EXEC: Realism Pack totals
    slippage_total: float = 0.0
    latency_total: float = 0.0
    reject_total: float = 0.0
    partial_fill_total: float = 0.0
    
    # EXEC: StopReason Single Truth Chain (SSOT)
    # Orchestrator가 유일한 소유자, 모든 파일에 동일하게 기록
    stop_reason: str = ""  # TIME_REACHED, MODEL_ANOMALY, FX_STALE, ERROR, USER_SIGINT
    stop_message: str = ""  # 상세 설명
    
    def bump_reject(self, reason: str) -> None:
        """
        Reject reason 카운트 증가
        
        Args:
            reason: reject 사유 키
        """
        if reason in self.reject_reasons:
            self.reject_reasons[reason] += 1
        else:
            self.reject_reasons["other"] += 1
    
    def record_trade(
        self,
        realized_pnl: float,
        fee: float,
        is_win: bool,
        net_pnl_full: Optional[float] = None
    ) -> None:
        """
        Trade 완료 시 PnL 기록 (net_pnl_full SSOT)
        
        Args:
            realized_pnl: 실현 PnL
            fee: 총 수수료
            is_win: 승/패 여부
            net_pnl_full: 마찰 포함 순손익 (미지정 시 realized_pnl fallback)
        """
        self.closed_trades += 1
        pnl_full = net_pnl_full if net_pnl_full is not None else realized_pnl
        self.net_pnl_full += pnl_full
        self.net_pnl = self.net_pnl_full
        self.fees += fee
        
        if is_win:
            self.wins += 1
        else:
            self.losses += 1
        
        # Winrate 계산
        if self.closed_trades > 0:
            self.winrate_pct = (self.wins / self.closed_trades) * 100

    def _record_sample(self, samples: List[float], value: float, max_size: int = 10000) -> None:
        """샘플 기록 (메모리 제한)"""
        samples.append(float(value))
        if len(samples) > max_size:
            samples.pop(0)

    def record_tick_timing(
        self,
        tick_elapsed_ms: float = 0.0,
        ticker_fetch_ms: float = 0.0,
        orderbook_fetch_ms: float = 0.0,
        decision_ms: float = 0.0,
        io_ms: float = 0.0,
        tick_compute_ms: Optional[float] = None,
        tick_interval_ms: Optional[float] = None,
        tick_sleep_ms: Optional[float] = None,
        md_upbit_ms: float = 0.0,
        md_binance_ms: float = 0.0,
        md_total_ms: float = 0.0,
        rate_limiter_wait_ms: float = 0.0,
        compute_decision_ms: Optional[float] = None,
    ) -> None:
        """Per-tick timing 기록 (PERF)"""
        if tick_compute_ms is None:
            tick_compute_ms = tick_elapsed_ms
        if tick_interval_ms is None:
            tick_interval_ms = tick_elapsed_ms
        if tick_sleep_ms is None and tick_interval_ms is not None:
            tick_sleep_ms = max(0.0, float(tick_interval_ms) - float(tick_compute_ms))
        if compute_decision_ms is None:
            compute_decision_ms = decision_ms

        if tick_interval_ms is not None:
            self._record_sample(self.tick_elapsed_ms_samples, tick_interval_ms)
            self._record_sample(self.tick_interval_ms_samples, tick_interval_ms)
        else:
            self._record_sample(self.tick_elapsed_ms_samples, tick_elapsed_ms)
        self._record_sample(self.tick_compute_ms_samples, tick_compute_ms)
        if tick_sleep_ms is not None:
            self._record_sample(self.tick_sleep_ms_samples, tick_sleep_ms)
        self._record_sample(self.tick_ticker_fetch_ms_samples, ticker_fetch_ms)
        self._record_sample(self.tick_orderbook_fetch_ms_samples, orderbook_fetch_ms)
        self._record_sample(self.tick_decision_ms_samples, decision_ms)
        self._record_sample(self.tick_io_ms_samples, io_ms)
        self._record_sample(self.md_upbit_ms_samples, md_upbit_ms)
        self._record_sample(self.md_binance_ms_samples, md_binance_ms)
        self._record_sample(self.md_total_ms_samples, md_total_ms)
        self._record_sample(self.compute_decision_ms_samples, compute_decision_ms)
        self._record_sample(self.rate_limiter_wait_ms_samples, rate_limiter_wait_ms)

    @staticmethod
    def _summarize_samples(samples: List[float]) -> Dict[str, float]:
        if not samples:
            return {
                "count": 0,
                "p50_ms": 0.0,
                "p95_ms": 0.0,
                "p99_ms": 0.0,
                "mean_ms": 0.0,
            }
        sorted_samples = sorted(samples)
        size = len(sorted_samples)
        p50 = sorted_samples[min(int(size * 0.50), size - 1)]
        p95 = sorted_samples[min(int(size * 0.95), size - 1)]
        p99 = sorted_samples[min(int(size * 0.99), size - 1)]
        mean = sum(sorted_samples) / size
        return {
            "count": size,
            "p50_ms": round(p50, 3),
            "p95_ms": round(p95, 3),
            "p99_ms": round(p99, 3),
            "mean_ms": round(mean, 3),
        }

    def _tick_timing_summary(self) -> Dict[str, Dict[str, float]]:
        return {
            "tick_elapsed": self._summarize_samples(self.tick_elapsed_ms_samples),
            "tick_compute": self._summarize_samples(self.tick_compute_ms_samples),
            "tick_interval": self._summarize_samples(self.tick_interval_ms_samples),
            "tick_sleep": self._summarize_samples(self.tick_sleep_ms_samples),
            "ticker_fetch": self._summarize_samples(self.tick_ticker_fetch_ms_samples),
            "orderbook_fetch": self._summarize_samples(self.tick_orderbook_fetch_ms_samples),
            "decision": self._summarize_samples(self.tick_decision_ms_samples),
            "io": self._summarize_samples(self.tick_io_ms_samples),
            "md_upbit": self._summarize_samples(self.md_upbit_ms_samples),
            "md_binance": self._summarize_samples(self.md_binance_ms_samples),
            "md_total": self._summarize_samples(self.md_total_ms_samples),
            "compute_decision": self._summarize_samples(self.compute_decision_ms_samples),
            "rate_limiter_wait": self._summarize_samples(self.rate_limiter_wait_ms_samples),
        }

    def sync_reject_total(self) -> int:
        """
        reject_total을 reject_reasons 합계로 동기화

        Returns:
            reject_total (int)
        """
        total = int(sum(self.reject_reasons.values()))
        self.reject_total = float(total)
        return total
    
    def to_dict(self) -> Dict[str, Any]:
        """
        KPI를 dict로 변환
        
        Returns:
            KPI dict (JSON 직렬화 가능)
        
        PERF: duration_seconds는 wallclock_start 기준 (정확한 wall-clock 시간)
        """
        # PERF: Wall-clock 기준 duration 계산
        duration_seconds = time.time() - self.wallclock_start
        
        reject_total = self.sync_reject_total()

        tick_timing = self._tick_timing_summary()

        kpi = {
            "start_time": datetime.fromtimestamp(self.wallclock_start).isoformat(),
            "duration_seconds": round(duration_seconds, 2),
            "duration_minutes": round(duration_seconds / 60, 2),
            "expected_duration_sec": round(self.expected_duration_sec, 2),
            "wallclock_drift_pct": round(self.wallclock_drift_pct, 2),
            "max_heartbeat_gap_sec": round(self.max_heartbeat_gap_sec, 2),
            "tick_timing_ms": tick_timing,
            "tick_elapsed_ms_p50": tick_timing["tick_elapsed"]["p50_ms"],
            "tick_elapsed_ms_p95": tick_timing["tick_elapsed"]["p95_ms"],
            "tick_elapsed_ms_p99": tick_timing["tick_elapsed"]["p99_ms"],
            "tick_compute_ms_p50": tick_timing["tick_compute"]["p50_ms"],
            "tick_compute_ms_p95": tick_timing["tick_compute"]["p95_ms"],
            "tick_compute_ms_p99": tick_timing["tick_compute"]["p99_ms"],
            "tick_interval_ms_p50": tick_timing["tick_interval"]["p50_ms"],
            "tick_interval_ms_p95": tick_timing["tick_interval"]["p95_ms"],
            "tick_interval_ms_p99": tick_timing["tick_interval"]["p99_ms"],
            "tick_sleep_ms_p50": tick_timing["tick_sleep"]["p50_ms"],
            "tick_sleep_ms_p95": tick_timing["tick_sleep"]["p95_ms"],
            "tick_sleep_ms_p99": tick_timing["tick_sleep"]["p99_ms"],
            "opportunities_generated": self.opportunities_generated,
            "intents_created": self.intents_created,
            "mock_executions": self.mock_executions,
            "paper_executions": self.paper_executions,
            "db_inserts_ok": self.db_inserts_ok,
            "db_inserts_failed": self.db_inserts_failed,
            "error_count": self.error_count,
            "errors": self.errors[:10],  # 최대 10개만
            "db_last_error": self.db_last_error,
            "memory_mb": self.memory_mb,
            "cpu_pct": self.cpu_pct,
            # EXEC: PnL 필드
            "closed_trades": self.closed_trades,
            "gross_pnl": round(self.gross_pnl, 2),
            "net_pnl": round(self.net_pnl_full, 2),
            "net_pnl_full": round(self.net_pnl_full, 2),
            "fees": round(self.fees, 2),
            "wins": self.wins,
            "losses": self.losses,
            "winrate_pct": round(self.winrate_pct, 2),
            # EXEC: Real MarketData 증거
            "marketdata_mode": self.marketdata_mode,
            "upbit_marketdata_ok": self.upbit_marketdata_ok,
            "binance_marketdata_ok": self.binance_marketdata_ok,
            "real_ticks_ok_count": self.real_ticks_ok_count,
            "real_ticks_fail_count": self.real_ticks_fail_count,
            # EXEC: Redis 지표
            "redis_ok": self.redis_ok,
            "ratelimit_hits": self.ratelimit_hits,
            "dedup_hits": self.dedup_hits,
            "rest_in_tick_count": int(self.rest_in_tick_count),
            # EXEC: Decision Trace
            "reject_reasons": dict(self.reject_reasons),
            # EXEC: FX Rate Info
            "fx_rate": round(self.fx_rate, 4),
            "fx_rate_source": self.fx_rate_source,
            "fx_rate_age_sec": round(self.fx_rate_age_sec, 2),
            "fx_rate_timestamp": self.fx_rate_timestamp,
            "fx_rate_degraded": self.fx_rate_degraded,
            # EXEC: Friction Costs
            "fees_total": round(self.fees_total, 4),
            "slippage_cost": round(self.slippage_cost, 4),
            "latency_cost": round(self.latency_cost, 4),
            "partial_fill_penalty": round(self.partial_fill_penalty, 4),
            "spread_cost": round(self.spread_cost, 4),
            "exec_cost_total": round(self.exec_cost_total, 4),
            # EXEC: Realism Pack totals
            "slippage_total": round(self.slippage_total, 4),
            "latency_total": round(self.latency_total, 4),
            "reject_total": reject_total,
            "partial_fill_total": round(self.partial_fill_total, 4),
            # EXEC: StopReason Single Truth Chain
            "stop_reason": self.stop_reason,
            "stop_message": self.stop_message,
        }
        
        # 시스템 메트릭 (psutil 있으면)
        if psutil:
            try:
                process = psutil.Process()
                kpi["memory_mb"] = round(process.memory_info().rss / 1024 / 1024, 2)
                kpi["cpu_pct"] = round(process.cpu_percent(interval=0.1), 2)
            except Exception:
                pass  # psutil 실패해도 계속
        
        return kpi
