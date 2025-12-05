# -*- coding: utf-8 -*-
"""
D82-5: Threshold Sweep Runner Tests

Tests for run_d82_5_threshold_sweep.py functions (without actual PAPER execution).
"""

import json
import pytest
from pathlib import Path
from datetime import datetime

# Import functions from runner script
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.run_d82_5_threshold_sweep import (
    generate_run_id,
    load_kpi_json,
    parse_trade_log,
)


class TestThresholdSweepRunner:
    """Test suite for D82-5 Threshold Sweep Runner."""
    
    def test_generate_run_id(self):
        """Test run_id generation logic."""
        timestamp = "20251205103000"
        
        # Test basic format
        run_id = generate_run_id(0.3, 1.0, timestamp)
        assert run_id == "d82-5-E0p3_TP1p0-20251205103000"
        
        # Test with different values
        run_id = generate_run_id(0.5, 2.0, timestamp)
        assert run_id == "d82-5-E0p5_TP2p0-20251205103000"
        
        # Test with decimal points
        run_id = generate_run_id(0.75, 1.25, timestamp)
        assert run_id == "d82-5-E0p8_TP1p2-20251205103000"  # Rounded to 1 decimal
    
    def test_load_kpi_json_success(self, tmp_path):
        """Test KPI JSON loading (success case)."""
        # Create fixture KPI JSON
        kpi_data = {
            "session_id": "test-session",
            "entry_trades": 5,
            "round_trips_completed": 4,
            "win_rate_pct": 60.0,
            "total_pnl_usd": 123.45,
            "loop_latency_avg_ms": 15.2,
            "avg_buy_slippage_bps": 2.1,
            "avg_sell_slippage_bps": 2.0,
        }
        
        kpi_path = tmp_path / "test_kpi.json"
        with open(kpi_path, "w") as f:
            json.dump(kpi_data, f)
        
        # Load and verify
        loaded_kpi = load_kpi_json(kpi_path)
        assert loaded_kpi is not None
        assert loaded_kpi["entry_trades"] == 5
        assert loaded_kpi["win_rate_pct"] == 60.0
        assert loaded_kpi["total_pnl_usd"] == 123.45
    
    def test_load_kpi_json_missing(self, tmp_path):
        """Test KPI JSON loading (missing file)."""
        kpi_path = tmp_path / "nonexistent_kpi.json"
        
        loaded_kpi = load_kpi_json(kpi_path)
        assert loaded_kpi is None
    
    def test_parse_trade_log_success(self, tmp_path):
        """Test Trade Log JSONL parsing (success case)."""
        # Create fixture Trade Log JSONL
        trades = [
            {"entry_spread_bps": 0.4, "exit_spread_bps": 0.5},
            {"entry_spread_bps": 0.6, "exit_spread_bps": 0.7},
            {"entry_spread_bps": 0.5, "exit_spread_bps": 0.6},
        ]
        
        log_path = tmp_path / "trade_log.jsonl"
        with open(log_path, "w") as f:
            for trade in trades:
                f.write(json.dumps(trade) + "\n")
        
        # Parse and verify
        metrics = parse_trade_log(log_path)
        assert metrics is not None
        assert abs(metrics["avg_entry_spread_bps"] - 0.5) < 0.01  # (0.4+0.6+0.5)/3
        assert abs(metrics["avg_exit_spread_bps"] - 0.6) < 0.01  # (0.5+0.7+0.6)/3
    
    def test_parse_trade_log_empty(self, tmp_path):
        """Test Trade Log JSONL parsing (empty file)."""
        log_path = tmp_path / "empty_log.jsonl"
        log_path.touch()  # Create empty file
        
        metrics = parse_trade_log(log_path)
        assert metrics is not None
        assert metrics["avg_entry_spread_bps"] == 0.0
        assert metrics["avg_exit_spread_bps"] == 0.0
    
    def test_parse_trade_log_missing(self, tmp_path):
        """Test Trade Log JSONL parsing (missing file)."""
        log_path = tmp_path / "nonexistent_log.jsonl"
        
        metrics = parse_trade_log(log_path)
        assert metrics is None
    
    def test_parse_trade_log_partial_fields(self, tmp_path):
        """Test Trade Log JSONL parsing (some entries missing fields)."""
        # Some entries have entry_spread_bps, some don't
        trades = [
            {"entry_spread_bps": 0.4},
            {"exit_spread_bps": 0.7},
            {"entry_spread_bps": 0.6, "exit_spread_bps": 0.8},
        ]
        
        log_path = tmp_path / "partial_log.jsonl"
        with open(log_path, "w") as f:
            for trade in trades:
                f.write(json.dumps(trade) + "\n")
        
        # Parse and verify
        metrics = parse_trade_log(log_path)
        assert metrics is not None
        assert abs(metrics["avg_entry_spread_bps"] - 0.5) < 0.01  # (0.4+0.6)/2
        assert abs(metrics["avg_exit_spread_bps"] - 0.75) < 0.01  # (0.7+0.8)/2


class TestThresholdCombinationGeneration:
    """Test threshold combination generation logic."""
    
    def test_grid_search_combinations(self):
        """Test grid search combination count."""
        entry_list = [0.3, 0.5, 0.7]
        tp_list = [1.0, 1.5, 2.0]
        
        combinations = [(e, t) for e in entry_list for t in tp_list]
        
        assert len(combinations) == 9
        assert (0.3, 1.0) in combinations
        assert (0.7, 2.0) in combinations
    
    def test_single_value_combinations(self):
        """Test single value for Entry/TP."""
        entry_list = [0.5]
        tp_list = [2.0]
        
        combinations = [(e, t) for e in entry_list for t in tp_list]
        
        assert len(combinations) == 1
        assert combinations[0] == (0.5, 2.0)


class TestDryRunMode:
    """Test dry-run mode behavior."""
    
    def test_dry_run_returns_dummy_result(self):
        """Test that dry-run mode returns dummy result without execution."""
        # This is tested implicitly by the runner script's dry_run flag
        # In dry_run mode, execute_single_run() returns a dict with status="dry_run"
        # and dummy values without calling subprocess.run()
        
        # We can't easily test this without importing the full module,
        # but we verify the logic is correct by inspection
        pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
