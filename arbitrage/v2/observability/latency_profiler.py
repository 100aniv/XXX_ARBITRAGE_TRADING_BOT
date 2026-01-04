"""
D205-11-1: Latency Profiler v1

목적:
- Tick → Decision → OrderIntent → Adapter → Fill/Record 구간을 ms 단위로 계측
- stage별 p50/p95/p99/max/count 집계
- Evidence로 남겨서 비용 모델(특히 latency cost) 현실화

설계 원칙:
- Hot path 오버헤드 최소 (기본 OFF, 옵션 켜면 ON)
- 엔진 내부에서 span 측정 (스크립트에서 time 찍지 않음)
- stage 이름은 고정 enum (문서/대시보드/자동 분석 호환)
- time.perf_counter() 사용 (마이크로초 단위 정밀도)
"""

import time
from enum import Enum
from typing import Dict, List, Optional
from dataclasses import dataclass, field
import logging

logger = logging.getLogger(__name__)


class LatencyStage(str, Enum):
    """레이턴시 측정 stage (고정 enum)"""
    RECEIVE_TICK = "RECEIVE_TICK"
    DECIDE = "DECIDE"
    ADAPTER_PLACE = "ADAPTER_PLACE"
    DB_RECORD = "DB_RECORD"


@dataclass
class LatencySpan:
    """단일 레이턴시 측정 span"""
    stage: LatencyStage
    start_time: float
    end_time: Optional[float] = None
    
    @property
    def duration_ms(self) -> float:
        """duration in milliseconds"""
        if self.end_time is None:
            return 0.0
        return (self.end_time - self.start_time) * 1000.0


@dataclass
class StageStats:
    """Stage별 레이턴시 통계"""
    stage: LatencyStage
    count: int = 0
    samples: List[float] = field(default_factory=list)
    
    def record(self, duration_ms: float):
        """샘플 기록 (rolling window)"""
        self.samples.append(duration_ms)
        self.count += 1
        
        # 메모리 제한 (최대 10000 샘플)
        if len(self.samples) > 10000:
            self.samples.pop(0)
    
    def get_p50(self) -> float:
        """p50 (median)"""
        if not self.samples:
            return 0.0
        sorted_samples = sorted(self.samples)
        idx = int(len(sorted_samples) * 0.50)
        return sorted_samples[min(idx, len(sorted_samples) - 1)]
    
    def get_p95(self) -> float:
        """p95"""
        if not self.samples:
            return 0.0
        sorted_samples = sorted(self.samples)
        idx = int(len(sorted_samples) * 0.95)
        return sorted_samples[min(idx, len(sorted_samples) - 1)]
    
    def get_p99(self) -> float:
        """p99"""
        if not self.samples:
            return 0.0
        sorted_samples = sorted(self.samples)
        idx = int(len(sorted_samples) * 0.99)
        return sorted_samples[min(idx, len(sorted_samples) - 1)]
    
    def get_max(self) -> float:
        """max"""
        if not self.samples:
            return 0.0
        return max(self.samples)
    
    def get_mean(self) -> float:
        """mean"""
        if not self.samples:
            return 0.0
        return sum(self.samples) / len(self.samples)
    
    def to_dict(self) -> Dict:
        """JSON 직렬화"""
        return {
            "stage": self.stage.value,
            "count": self.count,
            "p50_ms": round(self.get_p50(), 3),
            "p95_ms": round(self.get_p95(), 3),
            "p99_ms": round(self.get_p99(), 3),
            "max_ms": round(self.get_max(), 3),
            "mean_ms": round(self.get_mean(), 3),
        }


class LatencyProfiler:
    """
    레이턴시 프로파일러 (Engine-first)
    
    Usage:
        profiler = LatencyProfiler(enabled=True)
        
        # Span 시작
        profiler.start_span(LatencyStage.RECEIVE_TICK)
        # ... work ...
        profiler.end_span(LatencyStage.RECEIVE_TICK)
        
        # Snapshot (현재 통계)
        snapshot = profiler.snapshot()
    """
    
    def __init__(self, enabled: bool = True):
        """
        Args:
            enabled: True면 측정 활성화, False면 no-op
        """
        self.enabled = enabled
        self.stats: Dict[LatencyStage, StageStats] = {
            stage: StageStats(stage=stage) for stage in LatencyStage
        }
        self.active_spans: Dict[LatencyStage, LatencySpan] = {}
    
    def start_span(self, stage: LatencyStage):
        """
        Span 시작 (time.perf_counter 기반)
        
        Args:
            stage: 측정할 stage
        """
        if not self.enabled:
            return
        
        self.active_spans[stage] = LatencySpan(
            stage=stage,
            start_time=time.perf_counter()
        )
    
    def end_span(self, stage: LatencyStage):
        """
        Span 종료 + 통계 기록
        
        Args:
            stage: 종료할 stage
        """
        if not self.enabled:
            return
        
        span = self.active_spans.get(stage)
        if span is None:
            logger.warning(f"[LatencyProfiler] end_span called without start_span: {stage}")
            return
        
        span.end_time = time.perf_counter()
        duration_ms = span.duration_ms
        
        # 통계 기록
        self.stats[stage].record(duration_ms)
        
        # active span 제거
        del self.active_spans[stage]
    
    def snapshot(self) -> Dict[str, Dict]:
        """
        현재 통계 스냅샷 (JSON 직렬화 가능)
        
        Returns:
            {
                "RECEIVE_TICK": {"count": 100, "p50_ms": 1.2, ...},
                "DECIDE": {"count": 100, "p50_ms": 5.3, ...},
                ...
            }
        """
        return {
            stage.value: stats.to_dict()
            for stage, stats in self.stats.items()
        }
    
    def reset(self):
        """통계 초기화"""
        for stats in self.stats.values():
            stats.samples.clear()
            stats.count = 0
        self.active_spans.clear()
