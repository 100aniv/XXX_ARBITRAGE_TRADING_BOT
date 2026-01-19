"""
D205-18-2: Paper Metrics Collector (Engine-Centric)

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
from typing import Dict, List, Any
from datetime import datetime


@dataclass
class PaperMetrics:
    """
    Paper 실행 메트릭 수집기
    
    D205-18-2: PaperRunner에서 분리
    - Runner는 이 클래스 인스턴스만 참조
    - 모든 집계 로직은 여기에 집중
    
    D205-18-4R: Wallclock duration tracking 추가
    - start_time: 초기 생성 시간 (레거시)
    - wallclock_start: 실제 실행 시작 시간 (wall-clock 기준)
    """
    start_time: float = field(default_factory=time.time)
    wallclock_start: float = field(default_factory=time.time)  # D205-18-4R: Wall-clock 기준
    opportunities_generated: int = 0
    intents_created: int = 0
    mock_executions: int = 0
    db_inserts_ok: int = 0
    db_inserts_failed: int = 0
    error_count: int = 0
    errors: List[str] = field(default_factory=list)
    db_last_error: str = ""
    
    # D206-0 FIX: WARN=FAIL 카운터 (Evidence 저장용)
    warning_count: int = 0  # WarningCounterHandler에서 수집
    memory_mb: float = 0.0
    cpu_pct: float = 0.0
    
    # D205-3: PnL 필드
    closed_trades: int = 0
    gross_pnl: float = 0.0
    net_pnl: float = 0.0
    fees: float = 0.0
    wins: int = 0
    losses: int = 0
    winrate_pct: float = 0.0
    
    # D205-9: Real MarketData 증거
    marketdata_mode: str = "MOCK"  # MOCK or REAL
    upbit_marketdata_ok: bool = False
    binance_marketdata_ok: bool = False
    real_ticks_ok_count: int = 0
    real_ticks_fail_count: int = 0
    
    # D205-9 RECOVERY: Redis 지표
    redis_ok: bool = False
    ratelimit_hits: int = 0
    dedup_hits: int = 0
    
    # D205-10: Decision Trace (reject reason 카운트)
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
        "admin_paused": 0,  # D205-12-1: AdminControl reject
        "fx_stale": 0,
    })
    
    # D207-1-2: FX Rate Info (Economic Truth - Real-time FX)
    fx_rate: float = 0.0
    fx_rate_source: str = "unknown"
    fx_rate_age_sec: float = 0.0
    fx_rate_timestamp: str = ""
    fx_rate_degraded: bool = False
    
    # D207-1-3: Friction Costs (Economic Truth - Reality Model)
    fees_total: float = 0.0
    slippage_cost: float = 0.0
    latency_cost: float = 0.0
    partial_fill_penalty: float = 0.0
    
    # D207-1-5: StopReason Single Truth Chain (SSOT)
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
    
    def record_trade(self, realized_pnl: float, fee: float, is_win: bool) -> None:
        """
        Trade 완료 시 PnL 기록
        
        Args:
            realized_pnl: 실현 PnL
            fee: 총 수수료
            is_win: 승/패 여부
        """
        self.closed_trades += 1
        self.net_pnl += realized_pnl
        self.fees += fee
        
        if is_win:
            self.wins += 1
        else:
            self.losses += 1
        
        # Winrate 계산
        if self.closed_trades > 0:
            self.winrate_pct = (self.wins / self.closed_trades) * 100
    
    def to_dict(self) -> Dict[str, Any]:
        """
        KPI를 dict로 변환
        
        Returns:
            KPI dict (JSON 직렬화 가능)
        
        D205-18-4R: duration_seconds는 wallclock_start 기준 (정확한 wall-clock 시간)
        """
        # D205-18-4R: Wall-clock 기준 duration 계산
        duration_seconds = time.time() - self.wallclock_start
        
        kpi = {
            "start_time": datetime.fromtimestamp(self.wallclock_start).isoformat(),
            "duration_seconds": round(duration_seconds, 2),
            "duration_minutes": round(duration_seconds / 60, 2),
            "opportunities_generated": self.opportunities_generated,
            "intents_created": self.intents_created,
            "mock_executions": self.mock_executions,
            "db_inserts_ok": self.db_inserts_ok,
            "db_inserts_failed": self.db_inserts_failed,
            "error_count": self.error_count,
            "errors": self.errors[:10],  # 최대 10개만
            "db_last_error": self.db_last_error,
            "memory_mb": self.memory_mb,
            "cpu_pct": self.cpu_pct,
            # D205-3: PnL 필드
            "closed_trades": self.closed_trades,
            "gross_pnl": round(self.gross_pnl, 2),
            "net_pnl": round(self.net_pnl, 2),
            "fees": round(self.fees, 2),
            "wins": self.wins,
            "losses": self.losses,
            "winrate_pct": round(self.winrate_pct, 2),
            # D205-9: Real MarketData 증거
            "marketdata_mode": self.marketdata_mode,
            "upbit_marketdata_ok": self.upbit_marketdata_ok,
            "binance_marketdata_ok": self.binance_marketdata_ok,
            "real_ticks_ok_count": self.real_ticks_ok_count,
            "real_ticks_fail_count": self.real_ticks_fail_count,
            # D205-9 RECOVERY: Redis 지표
            "redis_ok": self.redis_ok,
            "ratelimit_hits": self.ratelimit_hits,
            "dedup_hits": self.dedup_hits,
            # D205-10: Decision Trace
            "reject_reasons": dict(self.reject_reasons),
            # D207-1-2: FX Rate Info
            "fx_rate": round(self.fx_rate, 4),
            "fx_rate_source": self.fx_rate_source,
            "fx_rate_age_sec": round(self.fx_rate_age_sec, 2),
            "fx_rate_timestamp": self.fx_rate_timestamp,
            "fx_rate_degraded": self.fx_rate_degraded,
            # D207-1-3: Friction Costs
            "fees_total": round(self.fees_total, 4),
            "slippage_cost": round(self.slippage_cost, 4),
            "latency_cost": round(self.latency_cost, 4),
            "partial_fill_penalty": round(self.partial_fill_penalty, 4),
            # D207-1-5: StopReason Single Truth Chain
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
