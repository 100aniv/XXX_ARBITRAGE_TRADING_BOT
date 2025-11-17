#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Metrics Module (PHASE D – MODULE D3 + D10)
===========================================

경량 메트릭 수집 및 노출 (Prometheus 형식 준비).

특징:
- 메모리 기반 메트릭 저장
- Prometheus 텍스트 형식 지원
- CSV/DB 기반 메트릭 계산
- 성능 및 지연 메트릭 (D10)
- 향후 HTTP /metrics 엔드포인트로 확장 가능 (D4)
"""

import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class MetricSnapshot:
    """메트릭 스냅샷"""
    timestamp: datetime
    total_pnl_krw: float            # 누적 손익 (KRW)
    win_rate: float                 # 승률 (0.0 ~ 1.0)
    num_trades: int                 # 거래 수
    num_open_positions: int         # 열린 포지션 수
    daily_pnl_krw: float            # 일일 손익 (KRW)
    avg_trade_duration_seconds: int # 평균 거래 지속 시간 (초)
    # D10 성능 메트릭
    loop_latency_ms: float = 0.0    # 루프 지연 (ms)
    ws_lag_ms: float = 0.0          # WebSocket 지연 (ms)
    redis_heartbeat_age_ms: float = 0.0  # Redis heartbeat 나이 (ms)
    num_live_trades_today: int = 0  # 오늘 실거래 수
    num_paper_trades_today: int = 0 # 오늘 모의거래 수
    last_live_trade_ts: str = ""    # 마지막 실거래 시간
    live_block_reasons: str = ""    # 실거래 차단 사유


def compute_basic_metrics(storage: Optional[Any] = None) -> MetricSnapshot:
    """기본 메트릭 계산
    
    Args:
        storage: BaseStorage 인스턴스 (CSV 또는 PostgreSQL)
    
    Returns:
        MetricSnapshot 객체
    
    PHASE D3: 간단한 구현 (대부분 0 또는 기본값)
    PHASE D4: 실제 DB/CSV 쿼리 기반 계산
    """
    now = datetime.now(timezone.utc)
    
    # TODO: 실제 구현 (D4)
    # - storage.load_positions() 호출
    # - 거래 기록 분석
    # - 손익 계산
    # - 승률 계산
    
    return MetricSnapshot(
        timestamp=now,
        total_pnl_krw=0.0,
        win_rate=0.0,
        num_trades=0,
        num_open_positions=0,
        daily_pnl_krw=0.0,
        avg_trade_duration_seconds=0
    )


def to_prometheus_format(snapshot: MetricSnapshot) -> str:
    """Prometheus 텍스트 형식으로 변환
    
    Args:
        snapshot: MetricSnapshot 객체
    
    Returns:
        Prometheus 형식 문자열
    
    예시:
        # HELP arbitrage_total_pnl_krw Total PnL in KRW
        # TYPE arbitrage_total_pnl_krw gauge
        arbitrage_total_pnl_krw 0.0
        ...
    """
    lines = []
    
    # 메트릭 정의
    metrics = {
        "arbitrage_total_pnl_krw": (
            "Total PnL in KRW",
            "gauge",
            snapshot.total_pnl_krw
        ),
        "arbitrage_win_rate": (
            "Win rate (0.0 ~ 1.0)",
            "gauge",
            snapshot.win_rate
        ),
        "arbitrage_num_trades": (
            "Total number of trades",
            "counter",
            snapshot.num_trades
        ),
        "arbitrage_num_open_positions": (
            "Number of open positions",
            "gauge",
            snapshot.num_open_positions
        ),
        "arbitrage_daily_pnl_krw": (
            "Daily PnL in KRW",
            "gauge",
            snapshot.daily_pnl_krw
        ),
        "arbitrage_avg_trade_duration_seconds": (
            "Average trade duration in seconds",
            "gauge",
            snapshot.avg_trade_duration_seconds
        ),
    }
    
    # 메트릭 출력
    for metric_name, (help_text, metric_type, value) in metrics.items():
        lines.append(f"# HELP {metric_name} {help_text}")
        lines.append(f"# TYPE {metric_name} {metric_type}")
        lines.append(f"{metric_name} {value}")
        lines.append("")
    
    # 타임스탬프 추가
    timestamp_ms = int(snapshot.timestamp.timestamp() * 1000)
    lines.append(f"# Timestamp: {timestamp_ms}")
    
    return "\n".join(lines)


def format_metrics_summary(snapshot: MetricSnapshot) -> str:
    """메트릭 요약 포맷팅 (로그용)
    
    Args:
        snapshot: MetricSnapshot 객체
    
    Returns:
        포맷된 요약 문자열
    """
    return (
        f"[METRICS] "
        f"pnl={snapshot.total_pnl_krw:,.0f}₩ "
        f"win_rate={snapshot.win_rate:.1%} "
        f"trades={snapshot.num_trades} "
        f"open_pos={snapshot.num_open_positions} "
        f"daily_pnl={snapshot.daily_pnl_krw:,.0f}₩ "
        f"avg_duration={snapshot.avg_trade_duration_seconds}s"
    )


class MetricsCollector:
    """메트릭 수집기"""
    
    def __init__(self, storage: Optional[Any] = None):
        """
        Args:
            storage: BaseStorage 인스턴스
        """
        self.storage = storage
        self.last_snapshot: Optional[MetricSnapshot] = None
        # D10 성능 메트릭
        self.loop_latency_ms = 0.0
        self.ws_lag_ms = 0.0
        self.redis_heartbeat_age_ms = 0.0
        self.num_live_trades_today = 0
        self.num_paper_trades_today = 0
        self.last_live_trade_ts = ""
        self.live_block_reasons = ""
    
    def collect(self) -> MetricSnapshot:
        """메트릭 수집
        
        Returns:
            MetricSnapshot 객체
        """
        self.last_snapshot = compute_basic_metrics(self.storage)
        return self.last_snapshot
    
    def get_prometheus_text(self) -> str:
        """Prometheus 형식 텍스트 반환
        
        Returns:
            Prometheus 형식 문자열
        """
        if self.last_snapshot is None:
            self.collect()
        
        return to_prometheus_format(self.last_snapshot)
    
    def get_summary(self) -> str:
        """메트릭 요약 반환
        
        Returns:
            포맷된 요약 문자열
        """
        if self.last_snapshot is None:
            self.collect()
        
        return format_metrics_summary(self.last_snapshot)
    
    def get_metrics(self) -> Dict[str, Any]:
        """메트릭 딕셔너리 반환
        
        Returns:
            메트릭 딕셔너리
        """
        if self.last_snapshot is None:
            self.collect()
        
        return {
            "pnl": int(self.last_snapshot.total_pnl_krw),
            "win_rate": self.last_snapshot.win_rate * 100,
            "num_trades": self.last_snapshot.num_trades,
            "open_positions": self.last_snapshot.num_open_positions,
            "daily_pnl": int(self.last_snapshot.daily_pnl_krw),
            "avg_duration": self.last_snapshot.avg_trade_duration_seconds
        }
    
    def add_safety_metrics(self, safety_stats: Dict[str, Any]):
        """안전 메트릭 추가 (D8)
        
        Args:
            safety_stats: SafetyValidator.get_safety_stats()
        """
        self.safety_stats = safety_stats
    
    def get_all_metrics(self) -> Dict[str, Any]:
        """전체 메트릭 반환 (기본 + 안전 + D10)
        
        Returns:
            전체 메트릭 딕셔너리
        """
        metrics = self.get_metrics()
        if hasattr(self, 'safety_stats'):
            metrics.update(self.safety_stats)
        # D10 성능 메트릭
        metrics.update({
            "loop_latency_ms": self.loop_latency_ms,
            "ws_lag_ms": self.ws_lag_ms,
            "redis_heartbeat_age_ms": self.redis_heartbeat_age_ms,
            "num_live_trades_today": self.num_live_trades_today,
            "num_paper_trades_today": self.num_paper_trades_today,
            "last_live_trade_ts": self.last_live_trade_ts,
            "live_block_reasons": self.live_block_reasons
        })
        return metrics
    
    def record_loop_timing(
        self,
        loop_start_time: float,
        loop_end_time: float,
        ws_last_tick: Optional[float] = None,
        redis_last_heartbeat: Optional[float] = None,
        is_live_trade: bool = False,
        live_status: Optional[Any] = None
    ):
        """루프 타이밍 기록 (D10)
        
        Args:
            loop_start_time: 루프 시작 시간 (time.monotonic())
            loop_end_time: 루프 종료 시간 (time.monotonic())
            ws_last_tick: WebSocket 마지막 틱 시간 (time.time())
            redis_last_heartbeat: Redis 마지막 heartbeat 시간 (time.time())
            is_live_trade: 실거래 여부
            live_status: LiveGuardStatus 객체
        """
        # 루프 지연
        self.loop_latency_ms = (loop_end_time - loop_start_time) * 1000
        
        # WebSocket 지연
        if ws_last_tick:
            self.ws_lag_ms = (time.time() - ws_last_tick) * 1000
        
        # Redis heartbeat 나이
        if redis_last_heartbeat:
            self.redis_heartbeat_age_ms = (time.time() - redis_last_heartbeat) * 1000
        
        # 거래 통계
        if is_live_trade:
            self.num_live_trades_today += 1
            self.last_live_trade_ts = datetime.now(timezone.utc).isoformat()
        else:
            self.num_paper_trades_today += 1
        
        # 실거래 차단 사유
        if live_status and hasattr(live_status, 'reason_blocked'):
            self.live_block_reasons = ";".join(live_status.reason_blocked) if live_status.reason_blocked else ""


# 글로벌 메트릭 수집기
_metrics_collector: Optional[MetricsCollector] = None


def get_metrics_collector(storage: Optional[Any] = None) -> MetricsCollector:
    """메트릭 수집기 싱글톤 반환
    
    Args:
        storage: BaseStorage 인스턴스
    
    Returns:
        MetricsCollector 인스턴스
    """
    global _metrics_collector
    if _metrics_collector is None:
        _metrics_collector = MetricsCollector(storage)
    return _metrics_collector


def reset_metrics_collector() -> None:
    """메트릭 수집기 리셋 (테스트용)"""
    global _metrics_collector
    _metrics_collector = None
