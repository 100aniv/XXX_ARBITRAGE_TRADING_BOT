#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Performance Profiling Module (PHASE D12)
========================================

루프 지연, WebSocket 지연, Redis 지연 등을 프로파일링하고
메트릭 시스템에 자동 통합.

특징:
- LoopProfiler: 루프 지연 (평균, P95, 최대)
- WebsocketLagProfiler: WS 지연 (이동 평균, 스파이크 감지)
- RedisLatencyProfiler: Redis heartbeat 나이 추적
"""

import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


class LoopProfiler:
    """루프 성능 프로파일러"""
    
    def __init__(self, window_size: int = 100):
        """
        Args:
            window_size: 히스토리 윈도우 크기
        """
        self.window_size = window_size
        self.latencies: List[float] = []
        self.total_loops = 0
    
    def record(self, latency_ms: float) -> None:
        """루프 지연 기록"""
        self.latencies.append(latency_ms)
        if len(self.latencies) > self.window_size:
            self.latencies.pop(0)
        self.total_loops += 1
    
    def get_avg_latency(self) -> float:
        """평균 루프 지연"""
        if not self.latencies:
            return 0.0
        return sum(self.latencies) / len(self.latencies)
    
    def get_p95_latency(self) -> float:
        """P95 루프 지연"""
        if not self.latencies:
            return 0.0
        sorted_latencies = sorted(self.latencies)
        idx = int(len(sorted_latencies) * 0.95)
        return sorted_latencies[min(idx, len(sorted_latencies) - 1)]
    
    def get_max_latency(self) -> float:
        """최대 루프 지연"""
        if not self.latencies:
            return 0.0
        return max(self.latencies)
    
    def get_metrics(self) -> Dict[str, float]:
        """메트릭 반환"""
        return {
            'loop_avg_ms': self.get_avg_latency(),
            'loop_p95_ms': self.get_p95_latency(),
            'loop_max_ms': self.get_max_latency()
        }


class WebsocketLagProfiler:
    """WebSocket 지연 프로파일러"""
    
    def __init__(self, window_size: int = 50):
        """
        Args:
            window_size: 이동 평균 윈도우 크기
        """
        self.window_size = window_size
        self.lags: List[float] = []
        self.spike_threshold_multiplier = 2.0  # 평균의 2배 이상을 스파이크로 간주
        self.spike_count = 0
    
    def record(self, lag_ms: float) -> None:
        """WS 지연 기록"""
        self.lags.append(lag_ms)
        if len(self.lags) > self.window_size:
            self.lags.pop(0)
        
        # 스파이크 감지
        if len(self.lags) >= 10:
            avg = sum(self.lags[:-1]) / len(self.lags[:-1])
            if lag_ms > avg * self.spike_threshold_multiplier:
                self.spike_count += 1
    
    def get_moving_avg(self) -> float:
        """이동 평균 WS 지연"""
        if not self.lags:
            return 0.0
        return sum(self.lags) / len(self.lags)
    
    def get_spike_count(self) -> int:
        """스파이크 감지 횟수"""
        return self.spike_count
    
    def get_metrics(self) -> Dict[str, Any]:
        """메트릭 반환"""
        return {
            'ws_lag_ma': self.get_moving_avg(),
            'ws_spike_count': self.spike_count
        }


class RedisLatencyProfiler:
    """Redis 지연 프로파일러"""
    
    def __init__(self, window_size: int = 50):
        """
        Args:
            window_size: 히스토리 윈도우 크기
        """
        self.window_size = window_size
        self.heartbeat_ages: List[float] = []
        self.max_age_observed = 0.0
    
    def record(self, heartbeat_age_ms: float) -> None:
        """Redis heartbeat 나이 기록"""
        self.heartbeat_ages.append(heartbeat_age_ms)
        if len(self.heartbeat_ages) > self.window_size:
            self.heartbeat_ages.pop(0)
        
        # 최대 나이 추적
        if heartbeat_age_ms > self.max_age_observed:
            self.max_age_observed = heartbeat_age_ms
    
    def get_avg_age(self) -> float:
        """평균 heartbeat 나이"""
        if not self.heartbeat_ages:
            return 0.0
        return sum(self.heartbeat_ages) / len(self.heartbeat_ages)
    
    def get_max_age(self) -> float:
        """최대 heartbeat 나이"""
        if not self.heartbeat_ages:
            return 0.0
        return max(self.heartbeat_ages)
    
    def get_trend(self) -> str:
        """추세 분석 (increasing, stable, decreasing)"""
        if len(self.heartbeat_ages) < 5:
            return "insufficient_data"
        
        recent_avg = sum(self.heartbeat_ages[-5:]) / 5
        older_avg = sum(self.heartbeat_ages[:5]) / 5
        
        if recent_avg > older_avg * 1.1:
            return "increasing"
        elif recent_avg < older_avg * 0.9:
            return "decreasing"
        else:
            return "stable"
    
    def get_metrics(self) -> Dict[str, Any]:
        """메트릭 반환"""
        return {
            'redis_heartbeat_avg_ms': self.get_avg_age(),
            'redis_heartbeat_max_ms': self.get_max_age(),
            'redis_heartbeat_trend': self.get_trend()
        }


class PerformanceProfiler:
    """통합 성능 프로파일러"""
    
    def __init__(self):
        """프로파일러 초기화"""
        self.loop_profiler = LoopProfiler()
        self.ws_profiler = WebsocketLagProfiler()
        self.redis_profiler = RedisLatencyProfiler()
    
    def record_loop(self, latency_ms: float) -> None:
        """루프 지연 기록"""
        self.loop_profiler.record(latency_ms)
    
    def record_ws_lag(self, lag_ms: float) -> None:
        """WS 지연 기록"""
        self.ws_profiler.record(lag_ms)
    
    def record_redis_heartbeat(self, age_ms: float) -> None:
        """Redis heartbeat 나이 기록"""
        self.redis_profiler.record(age_ms)
    
    def get_all_metrics(self) -> Dict[str, Any]:
        """모든 성능 메트릭 반환"""
        metrics = {}
        metrics.update(self.loop_profiler.get_metrics())
        metrics.update(self.ws_profiler.get_metrics())
        metrics.update(self.redis_profiler.get_metrics())
        return metrics
    
    def get_summary(self) -> str:
        """성능 요약 문자열"""
        loop_metrics = self.loop_profiler.get_metrics()
        ws_metrics = self.ws_profiler.get_metrics()
        redis_metrics = self.redis_profiler.get_metrics()
        
        return (
            f"Loop: avg={loop_metrics['loop_avg_ms']:.1f}ms, "
            f"p95={loop_metrics['loop_p95_ms']:.1f}ms, "
            f"max={loop_metrics['loop_max_ms']:.1f}ms | "
            f"WS: ma={ws_metrics['ws_lag_ma']:.1f}ms, "
            f"spikes={ws_metrics['ws_spike_count']} | "
            f"Redis: avg={redis_metrics['redis_heartbeat_avg_ms']:.1f}ms, "
            f"trend={redis_metrics['redis_heartbeat_trend']}"
        )
