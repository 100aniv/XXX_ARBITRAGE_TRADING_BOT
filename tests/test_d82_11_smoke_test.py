#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
D82-11: Smoke Test 테스트

테스트 범위:
1. 후보 로딩 & JSON 파싱
2. Top-N 선택 & 정렬
3. Run ID 생성
4. CLI 파싱 & dry-run 모드
5. KPI 파싱
6. Summary JSON 구조

Author: arbitrage-lite project
Date: 2025-12-05
"""

import json
import pytest
import sys
from pathlib import Path
from unittest.mock import patch, mock_open, MagicMock

# 프로젝트 루트 추가
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import modules
from scripts import run_d82_11_smoke_test as smoke_test


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def sample_candidates():
    """Sample candidates for testing."""
    return [
        {
            "entry_bps": 16,
            "tp_bps": 18,
            "edge_optimistic": 3.73,
            "edge_realistic": 3.73,
            "edge_conservative": 3.73,
            "is_structurally_safe": True,
            "is_recommended": True,
            "rationale": "Realistic Edge >= 0.5 bps (recommended)"
        },
        {
            "entry_bps": 14,
            "tp_bps": 18,
            "edge_optimistic": 2.73,
            "edge_realistic": 2.73,
            "edge_conservative": 2.73,
            "is_structurally_safe": True,
            "is_recommended": True,
            "rationale": "Realistic Edge >= 0.5 bps (recommended)"
        },
        {
            "entry_bps": 16,
            "tp_bps": 16,
            "edge_optimistic": 2.73,
            "edge_realistic": 2.73,
            "edge_conservative": 2.73,
            "is_structurally_safe": True,
            "is_recommended": True,
            "rationale": "Realistic Edge >= 0.5 bps (recommended)"
        },
        {
            "entry_bps": 12,
            "tp_bps": 16,
            "edge_optimistic": 0.73,
            "edge_realistic": 0.73,
            "edge_conservative": 0.73,
            "is_structurally_safe": True,
            "is_recommended": True,
            "rationale": "Realistic Edge >= 0.5 bps (recommended)"
        },
    ]


@pytest.fixture
def sample_kpi():
    """Sample KPI data for testing."""
    return {
        "run_id": "d82-11-600-E16p0_TP18p0-20251205215000",
        "entry_bps": 16.0,
        "tp_bps": 18.0,
        "duration_sec": 600,
        "round_trips_completed": 7,
        "win_rate_pct": 28.6,
        "exit_reasons": {
            "tp": 2,
            "stop_loss": 0,
            "time_limit": 5
        },
        "total_pnl_usd": 12.34,
        "avg_pnl_per_rt_usd": 1.76,
        "buy_fill_ratio_avg": 30.5,
        "sell_fill_ratio_avg": 100.0,
        "slippage_avg_bps": 2.14,
        "loop_latency_avg_ms": 18.5,
    }


# =============================================================================
# Test: Candidate Loading
# =============================================================================

def test_load_candidates_success(sample_candidates, tmp_path):
    """후보 로딩 성공 테스트."""
    # Create temp JSON file
    candidates_json = tmp_path / "candidates.json"
    with open(candidates_json, "w", encoding="utf-8") as f:
        json.dump({"candidates": sample_candidates}, f)
    
    # Load candidates
    loaded = smoke_test.load_recalibrated_candidates(candidates_json)
    
    assert len(loaded) == 4
    assert loaded[0]["entry_bps"] == 16
    assert loaded[0]["tp_bps"] == 18


def test_load_candidates_file_not_found():
    """후보 로딩 실패 (파일 없음) 테스트."""
    loaded = smoke_test.load_recalibrated_candidates(Path("nonexistent.json"))
    assert loaded == []


def test_load_candidates_invalid_json(tmp_path):
    """후보 로딩 실패 (잘못된 JSON) 테스트."""
    candidates_json = tmp_path / "invalid.json"
    with open(candidates_json, "w", encoding="utf-8") as f:
        f.write("invalid json{")
    
    loaded = smoke_test.load_recalibrated_candidates(candidates_json)
    assert loaded == []


# =============================================================================
# Test: Top-N Selection & Sorting
# =============================================================================

def test_select_top_n_sorting(sample_candidates):
    """Top-N 선택 및 정렬 테스트."""
    # Select top 2
    selected = smoke_test.select_top_n_candidates(sample_candidates, 2)
    
    assert len(selected) == 2
    
    # Should be sorted by edge_realistic (desc)
    assert selected[0]["edge_realistic"] == 3.73
    assert selected[1]["edge_realistic"] == 2.73
    
    # First should be (16, 18)
    assert selected[0]["entry_bps"] == 16
    assert selected[0]["tp_bps"] == 18


def test_select_top_n_more_than_available(sample_candidates):
    """Top-N이 후보 수보다 많을 때 테스트."""
    selected = smoke_test.select_top_n_candidates(sample_candidates, 10)
    assert len(selected) == 4  # Only 4 available


def test_select_top_n_zero():
    """Top-N = 0 테스트."""
    selected = smoke_test.select_top_n_candidates([], 0)
    assert len(selected) == 0


# =============================================================================
# Test: Run ID Generation
# =============================================================================

def test_generate_run_id():
    """Run ID 생성 테스트."""
    run_id = smoke_test.generate_run_id(600, 16.0, 18.0, "20251205215000")
    
    assert run_id == "d82-11-600-E16p0_TP18p0-20251205215000"
    assert "d82-11" in run_id
    assert "600" in run_id
    assert "E16p0" in run_id
    assert "TP18p0" in run_id


def test_generate_run_id_decimal():
    """Run ID 생성 (소수점) 테스트."""
    run_id = smoke_test.generate_run_id(1200, 14.5, 17.5, "20251205220000")
    
    assert "E14p5" in run_id
    assert "TP17p5" in run_id


# =============================================================================
# Test: Command Building
# =============================================================================

def test_build_command_basic():
    """커맨드 빌드 기본 테스트."""
    # Mock args
    args = MagicMock()
    args.duration_seconds = 600
    args.topn_size = 20
    args.output_dir = "logs/d82-11"
    args.enable_edge_monitor = False
    
    kpi_path = Path("logs/d82-11/runs/test_kpi.json")
    
    cmd, env = smoke_test.build_command(16.0, 18.0, "test_run", args, kpi_path)
    
    # Check command
    assert "python" in cmd[0]
    assert "run_d77_0_topn_arbitrage_paper.py" in cmd[1]
    assert "--duration-seconds" not in cmd  # Not in D77 runner
    assert "--run-duration-seconds" in cmd
    assert "600" in cmd
    
    # Check env vars
    assert env["ARBITRAGE_ENV"] == "paper"
    assert env["TOPN_ENTRY_MIN_SPREAD_BPS"] == "16.0"
    assert env["TOPN_EXIT_TP_SPREAD_BPS"] == "18.0"


def test_build_command_with_edge_monitor():
    """커맨드 빌드 (Edge Monitor 활성화) 테스트."""
    args = MagicMock()
    args.duration_seconds = 600
    args.topn_size = 20
    args.output_dir = "logs/d82-11"
    args.enable_edge_monitor = True
    
    kpi_path = Path("logs/d82-11/runs/test_kpi.json")
    
    cmd, env = smoke_test.build_command(16.0, 18.0, "test_run", args, kpi_path)
    
    assert env["ENABLE_RUNTIME_EDGE_MONITOR"] == "1"
    assert "EDGE_MONITOR_LOG_PATH" in env


# =============================================================================
# Test: KPI Parsing
# =============================================================================

def test_parse_kpi_file_success(sample_kpi, tmp_path):
    """KPI 파싱 성공 테스트."""
    kpi_path = tmp_path / "test_kpi.json"
    with open(kpi_path, "w", encoding="utf-8") as f:
        json.dump(sample_kpi, f)
    
    parsed = smoke_test.parse_kpi_file(kpi_path)
    
    assert parsed["round_trips_completed"] == 7
    assert parsed["win_rate_pct"] == 28.6
    assert abs(parsed["tp_exit_pct"] - 28.57) < 0.1  # 2/7 * 100
    assert abs(parsed["timeout_exit_pct"] - 71.43) < 0.1  # 5/7 * 100
    assert parsed["total_pnl_usd"] == 12.34


def test_parse_kpi_file_not_found():
    """KPI 파싱 실패 (파일 없음) 테스트."""
    parsed = smoke_test.parse_kpi_file(Path("nonexistent_kpi.json"))
    assert parsed == {}


# =============================================================================
# Test: Summary Generation
# =============================================================================

def test_generate_summary_basic():
    """Summary 생성 기본 테스트."""
    # Mock args
    args = MagicMock()
    args.duration_seconds = 600
    args.top_n = 2
    args.candidates_json = "logs/d82-10/candidates.json"
    
    # Mock results
    results = [
        {
            "entry_bps": 16,
            "tp_bps": 18,
            "edge_realistic": 3.73,
            "run_id": "run1",
            "kpi_path": "kpi1.json",
            "kpi_summary": {
                "round_trips_completed": 7,
                "total_pnl_usd": 12.34,
            },
            "status": "ok",
        },
        {
            "entry_bps": 14,
            "tp_bps": 18,
            "edge_realistic": 2.73,
            "run_id": "run2",
            "kpi_path": "kpi2.json",
            "kpi_summary": {
                "round_trips_completed": 5,
                "total_pnl_usd": 8.50,
            },
            "status": "ok",
        },
    ]
    
    summary = smoke_test.generate_summary(results, args)
    
    # Check metadata
    assert summary["metadata"]["duration_seconds"] == 600
    assert summary["metadata"]["top_n"] == 2
    
    # Check candidates
    assert len(summary["candidates"]) == 2
    
    # Check stats
    stats = summary["summary_stats"]
    assert stats["total_runs"] == 2
    assert stats["successful_runs"] == 2
    assert stats["failed_runs"] == 0
    assert stats["total_round_trips"] == 12  # 7 + 5
    assert abs(stats["avg_round_trips"] - 6.0) < 0.1  # 12 / 2
    assert abs(stats["total_pnl_usd"] - 20.84) < 0.1  # 12.34 + 8.50
    assert abs(stats["avg_pnl_usd"] - 10.42) < 0.1  # 20.84 / 2


def test_generate_summary_with_failures():
    """Summary 생성 (실패 포함) 테스트."""
    args = MagicMock()
    args.duration_seconds = 600
    args.top_n = 3
    args.candidates_json = "logs/d82-10/candidates.json"
    
    results = [
        {
            "entry_bps": 16,
            "tp_bps": 18,
            "kpi_summary": {"round_trips_completed": 7, "total_pnl_usd": 12.34},
            "status": "ok",
        },
        {
            "entry_bps": 14,
            "tp_bps": 18,
            "kpi_summary": {},
            "status": "error",
        },
        {
            "entry_bps": 16,
            "tp_bps": 16,
            "kpi_summary": {},
            "status": "timeout",
        },
    ]
    
    summary = smoke_test.generate_summary(results, args)
    
    stats = summary["summary_stats"]
    assert stats["total_runs"] == 3
    assert stats["successful_runs"] == 1
    assert stats["failed_runs"] == 2
    assert stats["total_round_trips"] == 7
    assert abs(stats["avg_round_trips"] - 7.0) < 0.1


# =============================================================================
# Test: CLI & Dry-run
# =============================================================================

def test_cli_dry_run(sample_candidates, tmp_path):
    """CLI dry-run 모드 테스트."""
    # Create temp candidates JSON
    candidates_json = tmp_path / "candidates.json"
    with open(candidates_json, "w", encoding="utf-8") as f:
        json.dump({"candidates": sample_candidates}, f)
    
    # Mock args
    args = MagicMock()
    args.duration_seconds = 30
    args.candidates_json = str(candidates_json)
    args.top_n = 2
    args.summary_output = None
    args.output_dir = str(tmp_path / "d82-11")
    args.topn_size = 20
    args.enable_edge_monitor = False
    args.dry_run = True
    
    # Load candidates
    candidates = smoke_test.load_recalibrated_candidates(Path(args.candidates_json))
    selected = smoke_test.select_top_n_candidates(candidates, args.top_n)
    
    # Execute single run in dry-run mode
    result = smoke_test.execute_single_run(selected[0], 1, len(selected), args)
    
    assert result["status"] == "dry_run"
    assert result["entry_bps"] == 16
    assert result["tp_bps"] == 18


# =============================================================================
# Run Tests
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
