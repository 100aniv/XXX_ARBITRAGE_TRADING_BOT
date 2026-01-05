"""
D205-11-1: LatencyProfiler 유닛 테스트

테스트 범위:
- quantile 계산 정확성 (p50/p95/p99)
- span 시작/종료 안정성
- enabled=False 시 no-op 동작
- 중첩 span 처리 (동일 stage 중복 start/end)
"""

import pytest
import time
from arbitrage.v2.observability import LatencyProfiler, LatencyStage


class TestLatencyProfiler:
    """LatencyProfiler 유닛 테스트"""
    
    def test_quantile_accuracy(self):
        """quantile 계산 정확성 (고정 샘플)"""
        profiler = LatencyProfiler(enabled=True)
        
        # 고정 샘플 (10, 20, 30, ..., 100)
        for i in range(1, 11):
            profiler.stats[LatencyStage.DECIDE].record(i * 10.0)
        
        stats = profiler.stats[LatencyStage.DECIDE]
        
        # p50 = 60.0 (idx=5, 0-indexed)
        assert stats.get_p50() == 60.0
        
        # p95 = 100.0 (idx=9, 0-indexed)
        assert stats.get_p95() == 100.0
        
        # p99 = 100.0 (idx=9, 0-indexed)
        assert stats.get_p99() == 100.0
        
        # max = 100.0
        assert stats.get_max() == 100.0
        
        # mean = 55.0
        assert stats.get_mean() == 55.0
    
    def test_span_lifecycle(self):
        """span 시작/종료 안정성"""
        profiler = LatencyProfiler(enabled=True)
        
        # Span 시작
        profiler.start_span(LatencyStage.RECEIVE_TICK)
        time.sleep(0.01)  # 10ms
        profiler.end_span(LatencyStage.RECEIVE_TICK)
        
        # 통계 확인
        stats = profiler.stats[LatencyStage.RECEIVE_TICK]
        assert stats.count == 1
        assert stats.get_mean() >= 9.0  # 최소 9ms (sleep 오차 허용)
        assert stats.get_mean() <= 20.0  # 최대 20ms (sleep 오차 허용)
    
    def test_no_op_when_disabled(self):
        """enabled=False 시 no-op 동작"""
        profiler = LatencyProfiler(enabled=False)
        
        # Span 시작/종료 (no-op)
        profiler.start_span(LatencyStage.DECIDE)
        time.sleep(0.01)
        profiler.end_span(LatencyStage.DECIDE)
        
        # 통계 확인 (count=0)
        stats = profiler.stats[LatencyStage.DECIDE]
        assert stats.count == 0
        assert len(stats.samples) == 0
    
    def test_end_without_start(self):
        """start 없이 end 호출 시 안정성 (warning만, crash 없음)"""
        profiler = LatencyProfiler(enabled=True)
        
        # end without start (warning만)
        profiler.end_span(LatencyStage.ADAPTER_PLACE)
        
        # 통계 확인 (count=0)
        stats = profiler.stats[LatencyStage.ADAPTER_PLACE]
        assert stats.count == 0
    
    def test_snapshot_format(self):
        """snapshot JSON 직렬화 가능"""
        profiler = LatencyProfiler(enabled=True)
        
        # 샘플 기록
        profiler.stats[LatencyStage.DB_RECORD].record(1.5)
        profiler.stats[LatencyStage.DB_RECORD].record(2.5)
        profiler.stats[LatencyStage.DB_RECORD].record(3.5)
        
        # Snapshot
        snapshot = profiler.snapshot()
        
        # 구조 확인
        assert "DB_RECORD" in snapshot
        assert "p50_ms" in snapshot["DB_RECORD"]
        assert "p95_ms" in snapshot["DB_RECORD"]
        assert "p99_ms" in snapshot["DB_RECORD"]
        assert "max_ms" in snapshot["DB_RECORD"]
        assert "mean_ms" in snapshot["DB_RECORD"]
        assert "count" in snapshot["DB_RECORD"]
        
        # 값 확인
        assert snapshot["DB_RECORD"]["count"] == 3
        assert snapshot["DB_RECORD"]["p50_ms"] == 2.5  # 중앙값
        assert snapshot["DB_RECORD"]["max_ms"] == 3.5
    
    def test_reset(self):
        """reset 동작 확인"""
        profiler = LatencyProfiler(enabled=True)
        
        # 샘플 기록
        profiler.stats[LatencyStage.RECEIVE_TICK].record(10.0)
        profiler.stats[LatencyStage.RECEIVE_TICK].record(20.0)
        
        # Reset
        profiler.reset()
        
        # 통계 확인 (모두 0)
        stats = profiler.stats[LatencyStage.RECEIVE_TICK]
        assert stats.count == 0
        assert len(stats.samples) == 0
    
    def test_memory_limit(self):
        """메모리 제한 (10000 샘플 초과 시 FIFO)"""
        profiler = LatencyProfiler(enabled=True)
        
        # 10001 샘플 기록
        for i in range(10001):
            profiler.stats[LatencyStage.DECIDE].record(float(i))
        
        # 샘플 개수 확인 (10000개로 제한)
        stats = profiler.stats[LatencyStage.DECIDE]
        assert len(stats.samples) == 10000
        assert stats.count == 10001  # count는 누적
        
        # 첫 샘플 제거 확인 (FIFO)
        assert stats.samples[0] == 1.0  # 0.0은 제거됨
    
    def test_multiple_stages(self):
        """Multiple stages"""
        profiler = LatencyProfiler(enabled=True)
        
        for _ in range(10):
            profiler.start_span(LatencyStage.RECEIVE_TICK)
            time.sleep(0.001)
            profiler.end_span(LatencyStage.RECEIVE_TICK)
            
            profiler.start_span(LatencyStage.DECIDE)
            time.sleep(0.0005)
            profiler.end_span(LatencyStage.DECIDE)
        
        snapshot = profiler.snapshot()
        
        assert len(snapshot) >= 2
        assert "RECEIVE_TICK" in snapshot
        assert "DECIDE" in snapshot
        
        # 통계 확인 (각 stage별 count=1)
        assert profiler.stats[LatencyStage.RECEIVE_TICK].count == 10
        assert profiler.stats[LatencyStage.DECIDE].count == 10
        # Snapshot
        snapshot = profiler.snapshot()
        assert len(snapshot) == 6  # 6개 stage (RECEIVE_TICK, DECIDE, ADAPTER_PLACE, DB_RECORD, REDIS_READ, REDIS_WRITE)
