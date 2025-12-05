#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
D82-10: Edge 재보정 테스트

테스트 범위:
1. Cost Profile 계산 로직
2. Edge 재계산 (시나리오별)
3. 후보 선정 기준
4. D82-9 조합 Edge 검증

Author: arbitrage-lite project
Date: 2025-12-05
"""

import json
import pytest
import sys
from pathlib import Path

# 프로젝트 루트 추가
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import modules
from scripts import recalibrate_d82_edge_model as edge_model


# =============================================================================
# Test: Scenario Parameters
# =============================================================================

def test_scenario_params_creation():
    """시나리오 파라미터 생성 테스트."""
    # Mock cost profile
    cost_profile = {
        "slippage_avg": 2.14,
        "slippage_median": 2.14,
        "slippage_p75": 2.14,
        "slippage_p90": 2.14,
        "slippage_p95": 2.14,
        "fee_total_bps": 9.0,
        "buy_fill_ratio_avg": 26.15,
        "buy_fill_ratio_p25": 26.15,
    }
    
    scenarios = edge_model.create_scenario_params(cost_profile)
    
    # Should have 3 scenarios
    assert len(scenarios) == 3
    assert edge_model.EdgeScenario.OPTIMISTIC in scenarios
    assert edge_model.EdgeScenario.REALISTIC in scenarios
    assert edge_model.EdgeScenario.CONSERVATIVE in scenarios
    
    # Check values
    opt = scenarios[edge_model.EdgeScenario.OPTIMISTIC]
    assert opt.slippage_bps == 2.14
    assert opt.fee_bps == 9.0
    assert abs(opt.buy_fill_ratio - 0.2615) < 0.001


# =============================================================================
# Test: Edge Calculation
# =============================================================================

def test_compute_theoretical_edge_basic():
    """기본 Edge 계산 테스트."""
    params = edge_model.ScenarioParams(
        scenario=edge_model.EdgeScenario.REALISTIC,
        slippage_bps=2.14,
        fee_bps=9.0,
        buy_fill_ratio=0.2615,
        description="Test"
    )
    
    # Case 1: Entry 14, TP 14 → Spread 14, Cost 13.28, Edge +0.72
    edge = edge_model.compute_theoretical_edge(14, 14, params)
    assert edge.gross_spread_bps == 14.0
    assert abs(edge.total_cost_bps - 13.28) < 0.01
    assert abs(edge.net_edge_bps - 0.72) < 0.01
    assert edge.is_viable is True
    assert edge.is_recommended is True  # >= 0.5
    
    # Case 2: Entry 10, TP 14 → Spread 12, Cost 13.28, Edge -1.28
    edge = edge_model.compute_theoretical_edge(10, 14, params)
    assert edge.gross_spread_bps == 12.0
    assert abs(edge.total_cost_bps - 13.28) < 0.01
    assert abs(edge.net_edge_bps - (-1.28)) < 0.01
    assert edge.is_viable is False
    assert edge.is_recommended is False


def test_compute_theoretical_edge_d82_9_combinations():
    """D82-9 실패 조합 Edge 검증."""
    params = edge_model.ScenarioParams(
        scenario=edge_model.EdgeScenario.REALISTIC,
        slippage_bps=2.14,
        fee_bps=9.0,
        buy_fill_ratio=0.2615,
        description="Test"
    )
    
    # D82-9 조합들은 모두 Edge < 0이어야 함
    d82_9_combinations = [
        (10, 13),  # Edge = 11.5 - 13.28 = -1.78
        (10, 14),  # Edge = 12.0 - 13.28 = -1.28
        (10, 15),  # Edge = 12.5 - 13.28 = -0.78
        (12, 13),  # Edge = 12.5 - 13.28 = -0.78
        (12, 14),  # Edge = 13.0 - 13.28 = -0.28
    ]
    
    for entry, tp in d82_9_combinations:
        edge = edge_model.compute_theoretical_edge(entry, tp, params)
        assert edge.is_viable is False, f"Entry {entry}, TP {tp} should have Edge < 0"
        assert edge.net_edge_bps < 0, f"Entry {entry}, TP {tp} Edge should be negative"


def test_compute_theoretical_edge_recommended_combinations():
    """추천 후보 조합 Edge 검증."""
    params = edge_model.ScenarioParams(
        scenario=edge_model.EdgeScenario.REALISTIC,
        slippage_bps=2.14,
        fee_bps=9.0,
        buy_fill_ratio=0.2615,
        description="Test"
    )
    
    # 추천 후보들은 Edge >= 0.5이어야 함
    recommended = [
        (16, 18),  # Edge = 17 - 13.28 = +3.72
        (14, 18),  # Edge = 16 - 13.28 = +2.72
        (16, 16),  # Edge = 16 - 13.28 = +2.72
    ]
    
    for entry, tp in recommended:
        edge = edge_model.compute_theoretical_edge(entry, tp, params)
        assert edge.is_viable is True, f"Entry {entry}, TP {tp} should be viable"
        assert edge.is_recommended is True, f"Entry {entry}, TP {tp} should be recommended"
        assert edge.net_edge_bps >= 0.5, f"Entry {entry}, TP {tp} Edge should be >= 0.5"


# =============================================================================
# Test: Candidate Grid
# =============================================================================

def test_generate_candidate_grid():
    """후보 Grid 생성 테스트."""
    grid = edge_model.generate_candidate_grid()
    
    # Should have combinations
    assert len(grid) > 0
    
    # All should satisfy Entry <= TP
    for entry, tp in grid:
        assert entry <= tp, f"Entry {entry} should be <= TP {tp}"
    
    # Should include some high-edge combinations
    assert (14, 14) in grid
    assert (16, 18) in grid
    assert (14, 18) in grid


# =============================================================================
# Test: Candidate Selection
# =============================================================================

def test_select_recalibrated_candidates():
    """후보 선정 로직 테스트."""
    # Create dummy edge calculations
    params = edge_model.ScenarioParams(
        scenario=edge_model.EdgeScenario.REALISTIC,
        slippage_bps=2.14,
        fee_bps=9.0,
        buy_fill_ratio=0.2615,
        description="Test"
    )
    
    grid = [(14, 14), (14, 16), (10, 14), (12, 12)]
    edge_calculations = {}
    
    for entry, tp in grid:
        edge_calculations[(entry, tp)] = {}
        for scenario in edge_model.EdgeScenario:
            edge = edge_model.compute_theoretical_edge(entry, tp, params)
            edge_calculations[(entry, tp)][scenario] = edge
    
    # Select candidates
    candidates = edge_model.select_recalibrated_candidates(edge_calculations)
    
    # Should select only Edge >= 0 combinations
    for candidate in candidates:
        assert candidate.is_structurally_safe is True
        assert candidate.edge_conservative >= 0
    
    # Should exclude (10, 14) - Edge < 0
    candidate_tuples = [(c.entry_bps, c.tp_bps) for c in candidates]
    assert (10, 14) not in candidate_tuples
    
    # Should include (14, 16) - Edge > 0
    assert (14, 16) in candidate_tuples


def test_recalibrated_candidate_rationale():
    """후보 Rationale 생성 테스트."""
    params = edge_model.ScenarioParams(
        scenario=edge_model.EdgeScenario.REALISTIC,
        slippage_bps=2.14,
        fee_bps=9.0,
        buy_fill_ratio=0.2615,
        description="Test"
    )
    
    # High edge candidate
    edges = {
        edge_model.EdgeScenario.OPTIMISTIC: edge_model.compute_theoretical_edge(16, 18, params),
        edge_model.EdgeScenario.REALISTIC: edge_model.compute_theoretical_edge(16, 18, params),
        edge_model.EdgeScenario.CONSERVATIVE: edge_model.compute_theoretical_edge(16, 18, params),
    }
    
    edge_calculations = {(16, 18): edges}
    candidates = edge_model.select_recalibrated_candidates(edge_calculations)
    
    assert len(candidates) == 1
    candidate = candidates[0]
    
    # Should be recommended
    assert candidate.is_recommended is True
    assert "Realistic Edge >= 0.5 bps" in candidate.rationale


# =============================================================================
# Test: JSON Output
# =============================================================================

def test_json_output_structure():
    """JSON 출력 구조 테스트."""
    # Check if JSON files exist
    candidates_path = Path("logs/d82-10/recalibrated_tp_entry_candidates.json")
    report_path = Path("logs/d82-10/edge_recalibration_report.json")
    
    # Should exist after main script runs
    if candidates_path.exists():
        with open(candidates_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        # Check structure
        assert "metadata" in data
        assert "candidates" in data
        assert len(data["candidates"]) > 0
        
        # Check candidate fields
        candidate = data["candidates"][0]
        assert "entry_bps" in candidate
        assert "tp_bps" in candidate
        assert "edge_optimistic" in candidate
        assert "edge_realistic" in candidate
        assert "edge_conservative" in candidate
        assert "is_structurally_safe" in candidate
        assert "is_recommended" in candidate


# =============================================================================
# Run Tests
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
