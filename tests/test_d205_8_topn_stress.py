#!/usr/bin/env python3
"""
D205-8: TopN Stress 유닛 테스트 (진짜 실측 검증)

Purpose:
- TopNStressRunner 핵심 로직 검증
- Latency 측정, Queue 시뮬레이션, Throttling 검증
- StressMetrics 계산 검증

Author: arbitrage-lite V2
Date: 2026-01-01
"""

import pytest
from arbitrage.v2.harness.topn_stress import TopNStressRunner, StressMetrics


def test_stress_metrics_creation():
    """StressMetrics 생성 테스트"""
    metrics = StressMetrics(topn=10, duration_sec=60.0)
    
    assert metrics.topn == 10
    assert metrics.duration_sec == 60.0
    assert metrics.latencies_ms == []
    assert metrics.error_count == 0
    assert metrics.throttling_events == 0
    
    # to_dict 변환 테스트
    data = metrics.to_dict()
    assert data["topn"] == 10
    assert data["duration_minutes"] == 1.0
    assert "note" in data
    assert "Real measurement" in data["note"]


def test_stress_runner_percentile_calc():
    """백분위수 계산 검증"""
    runner = TopNStressRunner(topn=10, duration_minutes=1, output_dir="logs/test")
    
    # 빈 리스트
    assert runner._calc_percentile([], 95) == 0.0
    
    # 단일 값
    assert runner._calc_percentile([100.0], 95) == 100.0
    
    # 정렬된 값들
    values = [10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0, 100.0]
    p50 = runner._calc_percentile(values, 50)
    p95 = runner._calc_percentile(values, 95)
    p99 = runner._calc_percentile(values, 99)
    
    assert 40.0 <= p50 <= 60.0  # 중앙값 근처
    assert p95 >= 90.0  # 상위 5%
    assert p99 >= 95.0  # 상위 1%


def test_stress_runner_throttling_check():
    """Throttling 체크 로직 검증"""
    runner = TopNStressRunner(topn=10, duration_minutes=1, output_dir="logs/test")
    
    # 초기 상태: queue 비어 있음
    assert not runner._check_throttling()
    assert runner.metrics.throttling_events == 0
    
    # Queue 채우기 (threshold=100)
    for i in range(50):
        runner.queue.append(i)
    
    # 50개: throttling 안 됨
    assert not runner._check_throttling()
    assert runner.metrics.throttling_events == 0
    
    # 120개: throttling 발생
    for i in range(70):
        runner.queue.append(i)
    
    assert runner._check_throttling()
    assert runner.metrics.throttling_events == 1
    
    # 한 번 더 체크
    assert runner._check_throttling()
    assert runner.metrics.throttling_events == 2
