#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
D82-9: TP Fine-tuning 테스트

테스트 범위:
1. 후보 분석 스크립트 (analyze_d82_9_tp_candidates.py)
   - Effective Edge 계산
   - Trade Activity/Win Rate 추정
   - 조합 생성
   - 후보 선정
2. PAPER Runner (run_d82_9_paper_candidates_longrun.py)
   - Candidates JSON 로딩
   - Run ID 생성
   - Command 빌드

Author: arbitrage-lite project
Date: 2025-12-05
"""

import json
import pytest
import sys
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# 프로젝트 루트 추가
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import scripts as modules
from scripts import analyze_d82_9_tp_candidates as analysis_script
from scripts import run_d82_9_paper_candidates_longrun as runner_script


# =============================================================================
# Test: Effective Edge Calculation
# =============================================================================

def test_calculate_effective_edge():
    """Effective Edge 계산 테스트."""
    # Known values from D82-8
    # Slippage: 2.14 bps, Fee: 9.0 bps
    
    # Case 1: Entry 10, TP 13
    edge = analysis_script.calculate_effective_edge(10.0, 13.0)
    expected_spread = (10.0 + 13.0) / 2  # 11.5
    expected_edge = expected_spread - 2.14 - 9.0  # 0.36
    assert abs(edge - expected_edge) < 0.01, f"Expected {expected_edge}, got {edge}"
    
    # Case 2: Entry 12, TP 14
    edge = analysis_script.calculate_effective_edge(12.0, 14.0)
    expected_spread = (12.0 + 14.0) / 2  # 13.0
    expected_edge = expected_spread - 2.14 - 9.0  # 1.86
    assert abs(edge - expected_edge) < 0.01, f"Expected {expected_edge}, got {edge}"
    
    # Case 3: Entry 14, TP 15
    edge = analysis_script.calculate_effective_edge(14.0, 15.0)
    expected_spread = (14.0 + 15.0) / 2  # 14.5
    expected_edge = expected_spread - 2.14 - 9.0  # 3.36
    assert abs(edge - expected_edge) < 0.01, f"Expected {expected_edge}, got {edge}"


def test_estimate_trade_activity():
    """Entry threshold 기반 거래 활동 추정 테스트."""
    assert analysis_script.estimate_trade_activity(10.0) == "high"
    assert analysis_script.estimate_trade_activity(12.0) == "medium"
    assert analysis_script.estimate_trade_activity(14.0) == "low"
    assert analysis_script.estimate_trade_activity(16.0) == "low"


def test_estimate_win_rate():
    """TP threshold 기반 Win Rate 추정 테스트."""
    assert analysis_script.estimate_win_rate(10.0) == "high"
    assert analysis_script.estimate_win_rate(11.0) == "medium"
    assert analysis_script.estimate_win_rate(12.0) == "low"
    assert analysis_script.estimate_win_rate(15.0) == "low"


# =============================================================================
# Test: Candidate Generation
# =============================================================================

def test_generate_candidate_combinations():
    """후보 조합 생성 테스트."""
    combinations = analysis_script.generate_candidate_combinations()
    
    # 최소 개수 확인
    assert len(combinations) >= 4, f"Expected at least 4 combinations, got {len(combinations)}"
    
    # 모든 조합이 Entry <= TP 조건을 만족하는지 확인
    for combo in combinations:
        assert combo["entry_bps"] <= combo["tp_bps"], \
            f"Invalid combination: Entry {combo['entry_bps']} > TP {combo['tp_bps']}"
    
    # 특정 조합 포함 확인
    expected_combinations = [
        {"entry_bps": 10.0, "tp_bps": 13.0},
        {"entry_bps": 10.0, "tp_bps": 14.0},
        {"entry_bps": 12.0, "tp_bps": 13.0},
        {"entry_bps": 12.0, "tp_bps": 14.0},
    ]
    
    for expected in expected_combinations:
        found = any(
            c["entry_bps"] == expected["entry_bps"] and c["tp_bps"] == expected["tp_bps"]
            for c in combinations
        )
        assert found, f"Expected combination not found: {expected}"


def test_select_top_candidates():
    """상위 후보 선정 테스트."""
    # Mock candidates
    candidates = [
        analysis_script.ThresholdCandidate(
            entry_bps=10.0,
            tp_bps=13.0,
            rationale="Test 1",
            estimated_spread_bps=11.5,
            effective_edge_bps=0.36,
            structural_safety=True,
            priority=1,
            expected_trade_activity="high",
            expected_win_rate="low",
        ),
        analysis_script.ThresholdCandidate(
            entry_bps=10.0,
            tp_bps=14.0,
            rationale="Test 2",
            estimated_spread_bps=12.0,
            effective_edge_bps=0.86,
            structural_safety=True,
            priority=2,
            expected_trade_activity="high",
            expected_win_rate="low",
        ),
        analysis_script.ThresholdCandidate(
            entry_bps=10.0,
            tp_bps=10.0,
            rationale="Test 3 (unsafe)",
            estimated_spread_bps=10.0,
            effective_edge_bps=-1.14,
            structural_safety=False,
            priority=10,
            expected_trade_activity="high",
            expected_win_rate="high",
        ),
    ]
    
    # Select top 2
    selected = analysis_script.select_top_candidates(candidates, max_candidates=2)
    
    # Only safe candidates should be selected
    assert all(c.structural_safety for c in selected), "Unsafe candidates selected"
    
    # Priority order
    assert len(selected) == 2
    assert selected[0].priority == 1
    assert selected[1].priority == 2


# =============================================================================
# Test: PAPER Runner Functions
# =============================================================================

def test_generate_run_id():
    """Run ID 생성 테스트."""
    run_id = runner_script.generate_run_id(10.0, 13.0, "20251205120000")
    
    # Format check
    assert run_id.startswith("d82-9-"), f"Invalid prefix: {run_id}"
    assert "E10p0" in run_id, f"Entry not encoded correctly: {run_id}"
    assert "TP13p0" in run_id, f"TP not encoded correctly: {run_id}"
    assert "20251205120000" in run_id, f"Timestamp not included: {run_id}"
    
    # Test with decimals
    run_id2 = runner_script.generate_run_id(12.5, 14.5, "20251205120000")
    assert "E12p5" in run_id2
    assert "TP14p5" in run_id2


def test_load_candidates_json_not_found(tmp_path):
    """Candidates JSON 파일 없을 때 테스트."""
    non_existent = tmp_path / "non_existent.json"
    
    candidates = runner_script.load_candidates_json(non_existent)
    
    assert candidates == [], "Should return empty list for non-existent file"


def test_load_candidates_json_valid(tmp_path):
    """Candidates JSON 로딩 테스트 (정상)."""
    # Create mock JSON
    json_path = tmp_path / "candidates.json"
    mock_data = {
        "metadata": {
            "task": "D82-9",
            "total_candidates": 2,
        },
        "candidates": [
            {
                "entry_bps": 10.0,
                "tp_bps": 13.0,
                "rationale": "Test candidate 1",
                "effective_edge_bps": 0.36,
                "structural_safety": True,
                "priority": 1,
            },
            {
                "entry_bps": 12.0,
                "tp_bps": 14.0,
                "rationale": "Test candidate 2",
                "effective_edge_bps": 1.86,
                "structural_safety": True,
                "priority": 2,
            },
        ]
    }
    
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(mock_data, f)
    
    candidates = runner_script.load_candidates_json(json_path)
    
    assert len(candidates) == 2
    assert candidates[0]["entry_bps"] == 10.0
    assert candidates[0]["tp_bps"] == 13.0
    assert candidates[1]["entry_bps"] == 12.0
    assert candidates[1]["tp_bps"] == 14.0


def test_build_command():
    """Command 빌드 테스트."""
    # Mock args
    args = Mock()
    args.topn_size = 20
    args.run_duration_seconds = 1200
    args.enable_edge_monitor = True
    args.output_dir = "logs/d82-9"
    
    kpi_path = Path("logs/d82-9/runs/test_kpi.json")
    
    cmd, env = runner_script.build_command(
        entry_bps=10.0,
        tp_bps=13.0,
        run_id="test_run_id",
        args=args,
        kpi_path=kpi_path,
    )
    
    # Command check
    assert "python" in cmd[0]
    assert "run_d77_0_topn_arbitrage_paper.py" in str(cmd[1])
    assert "--data-source" in cmd
    assert "--topn-size" in cmd
    assert "20" in cmd
    
    # Environment variables check
    assert env["ARBITRAGE_ENV"] == "paper"
    assert env["TOPN_ENTRY_MIN_SPREAD_BPS"] == "10.0"
    assert env["TOPN_EXIT_TP_SPREAD_BPS"] == "13.0"
    assert "ENABLE_RUNTIME_EDGE_MONITOR" in env
    assert "EDGE_MONITOR_LOG_PATH" in env


# =============================================================================
# Integration Test (if needed)
# =============================================================================

def test_analyze_and_select_candidates_integration():
    """후보 분석 & 선정 통합 테스트."""
    selected = analysis_script.analyze_and_select_candidates()
    
    # Should return some candidates
    assert len(selected) > 0, "No candidates selected"
    assert len(selected) <= 5, "Too many candidates selected"
    
    # All should be structurally safe
    for candidate in selected:
        assert candidate.structural_safety, f"Unsafe candidate selected: {candidate}"
        assert candidate.effective_edge_bps > 0, f"Negative edge: {candidate}"


# =============================================================================
# Test: Runner Stability & KPI File Generation (D82-9B)
# =============================================================================

def test_runner_build_command():
    """Runner command 빌드 테스트."""
    import argparse
    
    # Mock args
    args = argparse.Namespace(
        topn_size=20,
        run_duration_seconds=60,
        enable_edge_monitor=True,
        output_dir="logs/d82-9",
    )
    
    entry_bps = 10.0
    tp_bps = 13.0
    run_id = "d82-9-E10p0_TP13p0-test"
    kpi_path = Path("logs/d82-9/runs/test_kpi.json")
    
    cmd, env_vars = runner_script.build_command(entry_bps, tp_bps, run_id, args, kpi_path)
    
    # Verify command structure
    assert "python" in cmd[0].lower(), "Python not in command"
    assert "run_d77_0_topn_arbitrage_paper.py" in cmd[1], "Runner script not found"
    assert "--data-source" in cmd, "--data-source missing"
    assert "real" in cmd, "data-source should be 'real'"
    assert "--topn-size" in cmd, "--topn-size missing"
    assert "--validation-profile" in cmd, "--validation-profile missing"
    assert "topn_research" in cmd, "validation-profile should be 'topn_research'"
    
    # Verify environment variables
    assert env_vars["ARBITRAGE_ENV"] == "paper", "ARBITRAGE_ENV incorrect"
    assert env_vars["TOPN_ENTRY_MIN_SPREAD_BPS"] == "10.0", "Entry threshold incorrect"
    assert env_vars["TOPN_EXIT_TP_SPREAD_BPS"] == "13.0", "TP threshold incorrect"
    assert env_vars["ENABLE_RUNTIME_EDGE_MONITOR"] == "1", "Edge monitor not enabled"


@patch('subprocess.run')
def test_runner_kpi_file_verification(mock_run):
    """Runner KPI 파일 검증 테스트."""
    import argparse
    import tempfile
    
    # Create temporary directory
    with tempfile.TemporaryDirectory() as tmpdir:
        # Track KPI path from build_command
        kpi_path_ref = [None]
        
        # Mock subprocess.run to create KPI file
        def create_kpi_file(cmd, *args, **kwargs):
            # Extract KPI path from command line
            try:
                kpi_idx = cmd.index("--kpi-output-path")
                kpi_path = Path(cmd[kpi_idx + 1])
            except (ValueError, IndexError):
                # Fallback: create in runs/
                runs_dir = Path(tmpdir) / "runs"
                runs_dir.mkdir(parents=True, exist_ok=True)
                from datetime import datetime
                timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
                kpi_path = runs_dir / f"d82-9-E10p0_TP13p0-{timestamp}_kpi.json"
            
            # Create KPI file
            kpi_path.parent.mkdir(parents=True, exist_ok=True)
            kpi_data = {
                "session_id": "test",
                "round_trips_completed": 5,
                "win_rate_pct": 50.0,
            }
            with open(kpi_path, "w") as f:
                json.dump(kpi_data, f)
            
            kpi_path_ref[0] = kpi_path
            
            # Return success
            return_value = MagicMock()
            return_value.returncode = 0
            return_value.stderr = ""
            return return_value
        
        mock_run.side_effect = create_kpi_file
        
        # Mock args
        args = argparse.Namespace(
            topn_size=20,
            run_duration_seconds=60,
            enable_edge_monitor=False,
            output_dir=tmpdir,
            dry_run=False,
        )
        
        # Mock candidate
        candidate = {
            "entry_bps": 10.0,
            "tp_bps": 13.0,
            "rationale": "Test candidate",
        }
        
        # Execute single run
        result = runner_script.execute_single_run(candidate, 1, 1, args)
        
        # Verify result
        assert result["status"] == "success", f"Expected success, got {result['status']}"
        assert result["kpi_exists"] is True, "KPI file should exist"
        assert result["kpi_size_bytes"] > 0, "KPI file should not be empty"


@patch('subprocess.run')
def test_runner_timeout_handling(mock_run):
    """Runner timeout 처리 테스트."""
    import argparse
    import subprocess
    
    # Mock subprocess.run to raise TimeoutExpired
    mock_run.side_effect = subprocess.TimeoutExpired(cmd=["python"], timeout=60)
    
    # Mock args
    args = argparse.Namespace(
        topn_size=20,
        run_duration_seconds=60,
        enable_edge_monitor=False,
        output_dir="logs/d82-9",
        dry_run=False,
    )
    
    # Mock candidate
    candidate = {
        "entry_bps": 10.0,
        "tp_bps": 13.0,
        "rationale": "Test candidate",
    }
    
    # Execute single run
    result = runner_script.execute_single_run(candidate, 1, 1, args)
    
    # Verify timeout handling
    assert result["status"] == "timeout", f"Expected timeout, got {result['status']}"
    assert "error" in result, "Error message should be present"


def test_runner_generate_run_id():
    """Runner run_id 생성 테스트."""
    timestamp = "20251205193220"
    
    # Test various combinations
    run_id_1 = runner_script.generate_run_id(10.0, 13.0, timestamp)
    assert run_id_1 == "d82-9-E10p0_TP13p0-20251205193220", f"Unexpected run_id: {run_id_1}"
    
    run_id_2 = runner_script.generate_run_id(12.5, 14.5, timestamp)
    assert run_id_2 == "d82-9-E12p5_TP14p5-20251205193220", f"Unexpected run_id: {run_id_2}"


# =============================================================================
# Run Tests
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
