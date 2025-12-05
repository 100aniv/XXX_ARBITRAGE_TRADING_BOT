#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
D82-11 Validation Pipeline Tests

Dry-run 모드로 Phase별 로직 검증
"""

import json
import pytest
from pathlib import Path
import sys

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.run_d82_11_validation_pipeline import (
    evaluate_phase1,
    evaluate_phase2,
    evaluate_phase3,
)


# =============================================================================
# Test Data Fixtures
# =============================================================================

@pytest.fixture
def sample_candidate():
    """Sample candidate data"""
    return {
        "entry_bps": 16,
        "tp_bps": 18,
        "edge_optimistic": 3.73,
        "edge_realistic": 3.73,
        "edge_conservative": 3.73,
        "run_id": "test-run-001",
        "kpi_path": "test.json",
        "status": "ok",
    }


@pytest.fixture
def passing_kpi():
    """KPI that passes Phase 1/2/3"""
    return {
        "round_trips_completed": 50,
        "wins": 15,
        "losses": 35,
        "win_rate_pct": 30.0,
        "total_pnl_usd": 500.0,
        "exit_reasons": {
            "take_profit": 20,
            "time_limit": 10,
            "stop_loss": 0,
            "spread_reversal": 0,
        },
        "loop_latency_avg_ms": 15.5,
        "loop_latency_p99_ms": 22.3,
    }


@pytest.fixture
def failing_kpi_low_rt():
    """KPI that fails due to low RT"""
    return {
        "round_trips_completed": 3,
        "wins": 0,
        "losses": 3,
        "win_rate_pct": 0.0,
        "total_pnl_usd": -1500.0,
        "exit_reasons": {
            "take_profit": 0,
            "time_limit": 3,
            "stop_loss": 0,
            "spread_reversal": 0,
        },
        "loop_latency_avg_ms": 15.5,
        "loop_latency_p99_ms": 22.3,
    }


@pytest.fixture
def failing_kpi_negative_pnl():
    """KPI that fails due to negative PnL"""
    return {
        "round_trips_completed": 20,
        "wins": 0,
        "losses": 20,
        "win_rate_pct": 0.0,
        "total_pnl_usd": -2500.0,
        "exit_reasons": {
            "take_profit": 0,
            "time_limit": 20,
            "stop_loss": 0,
            "spread_reversal": 0,
        },
        "loop_latency_avg_ms": 15.5,
        "loop_latency_p99_ms": 22.3,
    }


# =============================================================================
# Phase 1 Tests
# =============================================================================

def test_phase1_pass(sample_candidate, passing_kpi):
    """Phase 1 should pass with good KPI"""
    sample_candidate["kpi_summary"] = passing_kpi
    
    summary = {
        "candidates": [sample_candidate]
    }
    
    passed, pass_candidates, reason = evaluate_phase1(summary)
    
    assert passed is True
    assert len(pass_candidates) == 1
    assert "PASS" in reason


def test_phase1_fail_low_rt(sample_candidate, failing_kpi_low_rt):
    """Phase 1 should fail with RT < 5"""
    sample_candidate["kpi_summary"] = failing_kpi_low_rt
    
    summary = {
        "candidates": [sample_candidate]
    }
    
    passed, pass_candidates, reason = evaluate_phase1(summary)
    
    assert passed is False
    assert len(pass_candidates) == 0
    assert "RT=3 < 5" in reason or "FAIL" in reason


def test_phase1_partial_pass(sample_candidate, passing_kpi, failing_kpi_low_rt):
    """Phase 1 should pass if at least 1 candidate passes"""
    cand1 = sample_candidate.copy()
    cand1["kpi_summary"] = passing_kpi
    cand1["entry_bps"] = 16
    
    cand2 = sample_candidate.copy()
    cand2["kpi_summary"] = failing_kpi_low_rt
    cand2["entry_bps"] = 14
    
    summary = {
        "candidates": [cand1, cand2]
    }
    
    passed, pass_candidates, reason = evaluate_phase1(summary)
    
    assert passed is True
    assert len(pass_candidates) == 1
    assert pass_candidates[0]["entry_bps"] == 16


def test_phase1_boundary_rt_equals_5(sample_candidate):
    """Phase 1 boundary: RT = 5 should pass RT check"""
    kpi = {
        "round_trips_completed": 5,
        "wins": 1,
        "losses": 4,
        "win_rate_pct": 20.0,
        "total_pnl_usd": 100.0,
        "exit_reasons": {
            "take_profit": 1,
            "time_limit": 4,
        },
        "loop_latency_avg_ms": 15.0,
        "loop_latency_p99_ms": 23.0,
    }
    
    sample_candidate["kpi_summary"] = kpi
    
    summary = {
        "candidates": [sample_candidate]
    }
    
    passed, pass_candidates, reason = evaluate_phase1(summary)
    
    assert passed is True
    assert len(pass_candidates) == 1


# =============================================================================
# Phase 2 Tests
# =============================================================================

def test_phase2_pass(sample_candidate, passing_kpi):
    """Phase 2 should pass with good KPI"""
    sample_candidate["kpi_summary"] = passing_kpi
    
    summary = {
        "candidates": [sample_candidate]
    }
    
    passed, pass_candidates, reason = evaluate_phase2(summary)
    
    assert passed is True
    assert len(pass_candidates) == 1
    assert "PASS" in reason


def test_phase2_fail_negative_pnl(sample_candidate, failing_kpi_negative_pnl):
    """Phase 2 should fail with negative PnL"""
    sample_candidate["kpi_summary"] = failing_kpi_negative_pnl
    
    summary = {
        "candidates": [sample_candidate]
    }
    
    passed, pass_candidates, reason = evaluate_phase2(summary)
    
    assert passed is False
    assert len(pass_candidates) == 0


def test_phase2_boundary_rt_equals_10(sample_candidate):
    """Phase 2 boundary: RT = 10 should pass"""
    kpi = {
        "round_trips_completed": 10,
        "wins": 2,
        "losses": 8,
        "win_rate_pct": 20.0,
        "total_pnl_usd": 100.0,
        "exit_reasons": {
            "take_profit": 2,
            "time_limit": 8,
        },
        "loop_latency_avg_ms": 15.0,
        "loop_latency_p99_ms": 23.0,
    }
    
    sample_candidate["kpi_summary"] = kpi
    
    summary = {
        "candidates": [sample_candidate]
    }
    
    passed, pass_candidates, reason = evaluate_phase2(summary)
    
    assert passed is True


def test_phase2_boundary_wr_equals_10(sample_candidate):
    """Phase 2 boundary: WR = 10% should pass"""
    kpi = {
        "round_trips_completed": 20,
        "wins": 2,
        "losses": 18,
        "win_rate_pct": 10.0,
        "total_pnl_usd": 50.0,
        "exit_reasons": {
            "take_profit": 2,
            "time_limit": 18,
        },
        "loop_latency_avg_ms": 15.0,
        "loop_latency_p99_ms": 23.0,
    }
    
    sample_candidate["kpi_summary"] = kpi
    
    summary = {
        "candidates": [sample_candidate]
    }
    
    passed, pass_candidates, reason = evaluate_phase2(summary)
    
    assert passed is True


# =============================================================================
# Phase 3 Tests
# =============================================================================

def test_phase3_pass(sample_candidate, passing_kpi):
    """Phase 3 should pass with good KPI"""
    sample_candidate["kpi_summary"] = passing_kpi
    
    summary = {
        "candidates": [sample_candidate]
    }
    
    passed, reason = evaluate_phase3(summary)
    
    assert passed is True
    assert "PASS" in reason


def test_phase3_fail_high_latency(sample_candidate):
    """Phase 3 should fail with high latency"""
    kpi = {
        "round_trips_completed": 50,
        "wins": 15,
        "losses": 35,
        "win_rate_pct": 30.0,
        "total_pnl_usd": 500.0,
        "exit_reasons": {
            "take_profit": 20,
            "time_limit": 10,
        },
        "loop_latency_avg_ms": 20.0,
        "loop_latency_p99_ms": 35.0,  # > 25ms
    }
    
    sample_candidate["kpi_summary"] = kpi
    
    summary = {
        "candidates": [sample_candidate]
    }
    
    passed, reason = evaluate_phase3(summary)
    
    assert passed is False
    assert "Latency" in reason or "FAIL" in reason


def test_phase3_fail_tp_less_than_timeout(sample_candidate):
    """Phase 3 should fail if TP exits < Timeout exits"""
    kpi = {
        "round_trips_completed": 50,
        "wins": 10,
        "losses": 40,
        "win_rate_pct": 20.0,
        "total_pnl_usd": 200.0,
        "exit_reasons": {
            "take_profit": 5,
            "time_limit": 40,  # More than TP
        },
        "loop_latency_avg_ms": 15.0,
        "loop_latency_p99_ms": 22.0,
    }
    
    sample_candidate["kpi_summary"] = kpi
    
    summary = {
        "candidates": [sample_candidate]
    }
    
    passed, reason = evaluate_phase3(summary)
    
    assert passed is False


def test_phase3_boundary_rt_equals_30(sample_candidate):
    """Phase 3 boundary: RT = 30 should pass"""
    kpi = {
        "round_trips_completed": 30,
        "wins": 10,
        "losses": 20,
        "win_rate_pct": 33.3,
        "total_pnl_usd": 300.0,
        "exit_reasons": {
            "take_profit": 15,
            "time_limit": 10,
        },
        "loop_latency_avg_ms": 15.0,
        "loop_latency_p99_ms": 22.0,
    }
    
    sample_candidate["kpi_summary"] = kpi
    
    summary = {
        "candidates": [sample_candidate]
    }
    
    passed, reason = evaluate_phase3(summary)
    
    assert passed is True


def test_phase3_boundary_wr_equals_20(sample_candidate):
    """Phase 3 boundary: WR = 20% should pass"""
    kpi = {
        "round_trips_completed": 50,
        "wins": 10,
        "losses": 40,
        "win_rate_pct": 20.0,
        "total_pnl_usd": 100.0,
        "exit_reasons": {
            "take_profit": 25,
            "time_limit": 20,
        },
        "loop_latency_avg_ms": 15.0,
        "loop_latency_p99_ms": 22.0,
    }
    
    sample_candidate["kpi_summary"] = kpi
    
    summary = {
        "candidates": [sample_candidate]
    }
    
    passed, reason = evaluate_phase3(summary)
    
    assert passed is True


def test_phase3_boundary_latency_equals_24_99(sample_candidate):
    """Phase 3 boundary: Latency P99 = 24.99ms should pass"""
    kpi = {
        "round_trips_completed": 50,
        "wins": 15,
        "losses": 35,
        "win_rate_pct": 30.0,
        "total_pnl_usd": 500.0,
        "exit_reasons": {
            "take_profit": 25,
            "time_limit": 20,
        },
        "loop_latency_avg_ms": 15.0,
        "loop_latency_p99_ms": 24.99,
    }
    
    sample_candidate["kpi_summary"] = kpi
    
    summary = {
        "candidates": [sample_candidate]
    }
    
    passed, reason = evaluate_phase3(summary)
    
    assert passed is True


# =============================================================================
# Edge Cases
# =============================================================================

def test_empty_candidates():
    """Should handle empty candidates gracefully"""
    summary = {"candidates": []}
    
    passed, pass_candidates, reason = evaluate_phase1(summary)
    assert passed is False
    assert len(pass_candidates) == 0
    
    passed, pass_candidates, reason = evaluate_phase2(summary)
    assert passed is False
    assert len(pass_candidates) == 0
    
    passed, reason = evaluate_phase3(summary)
    assert passed is False


def test_missing_kpi_summary(sample_candidate):
    """Should handle missing KPI summary"""
    # No kpi_summary field
    summary = {"candidates": [sample_candidate]}
    
    passed, pass_candidates, reason = evaluate_phase1(summary)
    assert passed is False  # Missing KPI = FAIL
    
    passed, pass_candidates, reason = evaluate_phase2(summary)
    assert passed is False
    
    passed, reason = evaluate_phase3(summary)
    assert passed is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
