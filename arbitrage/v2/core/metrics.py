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
    
    D205-18-4R: Wall-Clock Duration 검증 필드 추가
    - start_time: phase 시작 시간 (wall-clock)
    - actual_duration_sec: 실제 실행 시간 (초)
    """
    start_time: float = field(default_factory=time.time)
    actual_duration_sec: float = 0.0  # Wall-clock 기반 실제 실행 시간
    opportunities_generated: int = 0
    intents_created: int = 0
    mock_executions: int = 0
    db_inserts_ok: int = 0
    db_inserts_failed: int = 0
    error_count: int = 0
    errors: List[str] = field(default_factory=list)
    db_last_error: str = ""
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
        "admin_paused": 0,  # D205-12-1: AdminControl reject
        "symbol_blacklisted": 0,  # D205-12-1: AdminControl reject
    })
    
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
        """
        duration_seconds = time.time() - self.start_time
        
        kpi = {
            "start_time": datetime.fromtimestamp(self.start_time).isoformat(),
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
