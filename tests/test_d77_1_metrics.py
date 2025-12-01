# -*- coding: utf-8 -*-
"""
D77-1: Prometheus Metrics Module Unit Tests

Test Coverage:
1. Metrics initialization
2. PnL recording
3. Trade recording (entry/exit)
4. Round trip counter
5. Win rate calculation
6. Loop latency (Summary)
7. Memory/CPU usage
8. Guard trigger recording
9. Alert recording
10. Metrics text output format
"""

import pytest
from prometheus_client import CollectorRegistry

from arbitrage.monitoring.metrics import (
    init_metrics,
    record_pnl,
    record_trade,
    record_round_trip,
    record_win_rate,
    record_loop_latency,
    record_memory_usage,
    record_cpu_usage,
    record_guard_trigger,
    record_alert,
    record_exit_reason,
    set_active_positions,
    get_metrics_text,
    reset_metrics,
)


@pytest.fixture(autouse=True)
def cleanup_metrics():
    """각 테스트 전후로 metrics 리셋"""
    reset_metrics()
    yield
    reset_metrics()


@pytest.fixture
def test_registry():
    """테스트용 CollectorRegistry"""
    return CollectorRegistry()


def test_init_metrics(test_registry):
    """메트릭 초기화 검증"""
    init_metrics(
        env="paper",
        universe="top20",
        strategy="topn_arb",
        registry=test_registry,
    )
    
    # 초기화만 했을 때는 HELP/TYPE만 노출됨
    text = get_metrics_text()
    
    # 기본 메트릭 HELP/TYPE 존재 확인
    assert "# HELP arb_topn_pnl_total" in text
    assert "# HELP arb_topn_win_rate" in text
    assert "# HELP arb_topn_round_trips_total" in text
    assert "# HELP arb_topn_loop_latency_seconds" in text
    
    # 값을 설정한 후 레이블 확인
    record_pnl(100.0)
    text = get_metrics_text()
    assert 'env="paper"' in text
    assert 'universe="top20"' in text
    assert 'strategy="topn_arb"' in text


def test_record_pnl(test_registry):
    """PnL 업데이트 검증"""
    init_metrics("paper", "top20", "topn_arb", registry=test_registry)
    
    record_pnl(100.0)
    text = get_metrics_text()
    assert "arb_topn_pnl_total" in text
    assert "100.0" in text
    
    record_pnl(250.5)
    text = get_metrics_text()
    assert "250.5" in text


def test_record_trades(test_registry):
    """Entry/Exit 거래 카운터 검증"""
    init_metrics("paper", "top20", "topn_arb", registry=test_registry)
    
    record_trade("entry")
    record_trade("entry")
    record_trade("exit")
    
    text = get_metrics_text()
    assert "arb_topn_trades_total" in text
    assert 'trade_type="entry"' in text
    assert 'trade_type="exit"' in text


def test_record_round_trip(test_registry):
    """라운드 트립 카운터 검증"""
    init_metrics("paper", "top20", "topn_arb", registry=test_registry)
    
    record_round_trip()
    record_round_trip()
    record_round_trip()
    
    text = get_metrics_text()
    assert "arb_topn_round_trips_total" in text
    # Counter는 증가만 가능, 실제 값은 3.0
    assert '3.0' in text or '3' in text


def test_record_win_rate(test_registry):
    """승률 계산 검증"""
    init_metrics("paper", "top20", "topn_arb", registry=test_registry)
    
    # 승률 0% (초기)
    record_win_rate(0, 0)
    text = get_metrics_text()
    assert "arb_topn_win_rate" in text
    
    # 승률 75% (3승 1패)
    record_win_rate(3, 1)
    text = get_metrics_text()
    assert "75.0" in text
    
    # 승률 100%
    record_win_rate(10, 0)
    text = get_metrics_text()
    assert "100.0" in text


def test_record_loop_latency(test_registry):
    """Summary 메트릭 검증"""
    init_metrics("paper", "top20", "topn_arb", registry=test_registry)
    
    # 여러 레이턴시 기록
    record_loop_latency(0.001)  # 1ms
    record_loop_latency(0.005)  # 5ms
    record_loop_latency(0.010)  # 10ms
    
    text = get_metrics_text()
    assert "arb_topn_loop_latency_seconds" in text
    assert "arb_topn_loop_latency_seconds_count" in text
    assert "arb_topn_loop_latency_seconds_sum" in text


def test_record_memory_cpu_usage(test_registry):
    """메모리/CPU 사용량 검증"""
    init_metrics("paper", "top20", "topn_arb", registry=test_registry)
    
    record_memory_usage(157286400)  # 150MB in bytes
    record_cpu_usage(35.5)
    
    text = get_metrics_text()
    assert "arb_topn_memory_usage_bytes" in text
    # Prometheus는 큰 숫자를 과학적 표기법으로 변환할 수 있음
    assert ("157286400" in text or "1.572864e+08" in text)
    assert "arb_topn_cpu_usage_percent" in text
    assert "35.5" in text


def test_record_guard_trigger(test_registry):
    """Guard 트리거 라벨 검증"""
    init_metrics("paper", "top20", "topn_arb", registry=test_registry)
    
    record_guard_trigger("exchange")
    record_guard_trigger("route")
    record_guard_trigger("exchange")
    
    text = get_metrics_text()
    assert "arb_topn_guard_triggers_total" in text
    assert 'guard_type="exchange"' in text
    assert 'guard_type="route"' in text


def test_record_alert(test_registry):
    """Alert 카운터 + 라벨 검증"""
    init_metrics("paper", "top20", "topn_arb", registry=test_registry)
    
    record_alert("P0", "rate_limiter")
    record_alert("P1", "health_monitor")
    record_alert("P2", "risk_guard")
    
    text = get_metrics_text()
    assert "arb_topn_alerts_total" in text
    assert 'severity="P0"' in text
    assert 'source="rate_limiter"' in text
    assert 'severity="P1"' in text
    assert 'source="health_monitor"' in text


def test_record_exit_reason(test_registry):
    """Exit 이유 기록 검증"""
    init_metrics("paper", "top20", "topn_arb", registry=test_registry)
    
    record_exit_reason("take_profit")
    record_exit_reason("take_profit")
    record_exit_reason("stop_loss")
    record_exit_reason("time_limit")
    
    text = get_metrics_text()
    assert "arb_topn_exit_reasons_total" in text
    assert 'reason="take_profit"' in text
    assert 'reason="stop_loss"' in text
    assert 'reason="time_limit"' in text


def test_set_active_positions(test_registry):
    """활성 포지션 수 검증"""
    init_metrics("paper", "top20", "topn_arb", registry=test_registry)
    
    set_active_positions(5)
    text = get_metrics_text()
    assert "arb_topn_active_positions" in text
    assert "5.0" in text
    
    set_active_positions(0)
    text = get_metrics_text()
    assert "0.0" in text


def test_metrics_text_output(test_registry):
    """/metrics 텍스트 포맷 검증"""
    init_metrics("paper", "top20", "topn_arb", registry=test_registry)
    
    record_pnl(1000.0)
    record_trade("entry")
    record_round_trip()
    
    text = get_metrics_text()
    
    # Prometheus 표준 포맷 확인
    assert "# HELP arb_topn_pnl_total" in text
    assert "# TYPE arb_topn_pnl_total gauge" in text
    assert "# HELP arb_topn_trades_total" in text
    assert "# TYPE arb_topn_trades_total counter" in text
    assert "# HELP arb_topn_round_trips_total" in text
    assert "# TYPE arb_topn_round_trips_total counter" in text


def test_reset_metrics():
    """메트릭 리셋 검증"""
    registry = CollectorRegistry()
    init_metrics("paper", "top20", "topn_arb", registry=registry)
    
    record_pnl(100.0)
    text1 = get_metrics_text()
    assert "arb_topn_pnl_total" in text1
    
    reset_metrics()
    text2 = get_metrics_text()
    assert text2 == ""  # 리셋 후 빈 문자열


def test_no_metrics_before_init():
    """초기화 전 호출 시 안전하게 무시"""
    reset_metrics()
    
    # 초기화 없이 호출해도 에러 없이 무시
    record_pnl(100.0)
    record_trade("entry")
    record_round_trip()
    
    text = get_metrics_text()
    assert text == ""  # 메트릭 없음


def test_multiple_environments(test_registry):
    """여러 환경 레이블 검증"""
    # Paper 환경
    init_metrics("paper", "top20", "topn_arb", registry=test_registry)
    record_pnl(100.0)
    
    text = get_metrics_text()
    assert 'env="paper"' in text
    assert 'universe="top20"' in text
    
    # 재초기화 (Live 환경으로 변경)
    reset_metrics()
    registry2 = CollectorRegistry()
    init_metrics("live", "top50", "topn_arb", registry=registry2)
    record_pnl(200.0)
    
    from arbitrage.monitoring.metrics import get_metrics_text as get_metrics_text2
    text2 = get_metrics_text()
    assert 'env="live"' in text2
    assert 'universe="top50"' in text2
