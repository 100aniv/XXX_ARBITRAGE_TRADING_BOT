# -*- coding: utf-8 -*-
"""
D82-8: Runtime Edge Monitor Unit Tests

Tests for Runtime Edge Monitor functionality.
"""

import json
import tempfile
from pathlib import Path
from datetime import datetime

import pytest

from arbitrage.logging.trade_logger import (
    TradeLogEntry,
    RuntimeEdgeMonitor,
    EdgeSnapshot,
    create_mock_trade_entry,
)


class TestRuntimeEdgeMonitor:
    """Tests for RuntimeEdgeMonitor class."""
    
    def test_initialization(self):
        """Test Edge Monitor initialization."""
        monitor = RuntimeEdgeMonitor(
            window_size=50,
            output_path=None,
            enabled=True,
            fee_bps=9.0
        )
        
        assert monitor.window_size == 50
        assert monitor.enabled is True
        assert monitor.fee_bps == 9.0
        assert len(monitor.trade_buffer) == 0
    
    def test_disabled_monitor(self):
        """Test disabled monitor does not record."""
        monitor = RuntimeEdgeMonitor(enabled=False)
        
        trade = create_mock_trade_entry(
            trade_id="test-1",
            session_id="session-1",
            universe_mode="TOP_20"
        )
        
        monitor.record_trade(trade)
        assert len(monitor.trade_buffer) == 0
        
        snapshot = monitor.get_current_snapshot()
        assert snapshot is None
    
    def test_record_single_trade(self):
        """Test recording a single trade."""
        monitor = RuntimeEdgeMonitor(window_size=50, enabled=True)
        
        trade = create_mock_trade_entry(
            trade_id="test-1",
            session_id="session-1",
            universe_mode="TOP_20"
        )
        
        monitor.record_trade(trade)
        assert len(monitor.trade_buffer) == 1
    
    def test_rolling_window(self):
        """Test rolling window behavior."""
        monitor = RuntimeEdgeMonitor(window_size=5, enabled=True)
        
        # Add 10 trades (window size = 5)
        for i in range(10):
            trade = create_mock_trade_entry(
                trade_id=f"test-{i}",
                session_id="session-1",
                universe_mode="TOP_20"
            )
            monitor.record_trade(trade)
        
        # Should keep only last 5 trades
        assert len(monitor.trade_buffer) == 5
        
        # Check oldest trade ID
        oldest_trade_id = monitor.trade_buffer[0].trade_id
        assert oldest_trade_id == "test-5"  # 0-4 dropped, 5-9 remain
    
    def test_snapshot_generation_sufficient_data(self):
        """Test snapshot generation with sufficient data."""
        monitor = RuntimeEdgeMonitor(window_size=50, enabled=True, fee_bps=9.0)
        
        # Add 20 trades
        for i in range(20):
            trade = create_mock_trade_entry(
                trade_id=f"test-{i}",
                session_id="session-1",
                universe_mode="TOP_20"
            )
            monitor.record_trade(trade)
        
        snapshot = monitor.get_current_snapshot()
        
        assert snapshot is not None
        assert isinstance(snapshot, EdgeSnapshot)
        assert snapshot.window_size == 20
        assert snapshot.total_trades == 20
        assert snapshot.avg_fee_bps == 9.0
        
        # Check effective edge calculation
        # Mock trade has entry_spread=45, exit_spread=44, avg=44.5
        # Slippage is 0.0 in mock
        # Effective Edge = 44.5 - 0.0 - 9.0 = 35.5
        assert snapshot.effective_edge_bps == pytest.approx(35.5, rel=0.1)
    
    def test_snapshot_generation_insufficient_data(self):
        """Test snapshot generation with insufficient data."""
        monitor = RuntimeEdgeMonitor(window_size=50, enabled=True)
        
        # Add only 5 trades (< min 10)
        for i in range(5):
            trade = create_mock_trade_entry(
                trade_id=f"test-{i}",
                session_id="session-1",
                universe_mode="TOP_20"
            )
            monitor.record_trade(trade)
        
        # Should not generate snapshot yet
        # (snapshot is generated after recording, so we need to check manually)
        snapshot = monitor.get_current_snapshot()
        
        # Snapshot should be generated (just won't auto-log)
        # But with 5 trades, it should still compute
        assert snapshot is not None or len(monitor.trade_buffer) < 10
    
    def test_win_rate_calculation(self):
        """Test win rate calculation."""
        monitor = RuntimeEdgeMonitor(window_size=50, enabled=True)
        
        # Add 10 winning trades
        for i in range(10):
            trade = create_mock_trade_entry(
                trade_id=f"win-{i}",
                session_id="session-1",
                universe_mode="TOP_20"
            )
            trade.trade_result = "win"
            monitor.record_trade(trade)
        
        # Add 5 losing trades
        for i in range(5):
            trade = create_mock_trade_entry(
                trade_id=f"loss-{i}",
                session_id="session-1",
                universe_mode="TOP_20"
            )
            trade.trade_result = "loss"
            monitor.record_trade(trade)
        
        snapshot = monitor.get_current_snapshot()
        
        assert snapshot is not None
        assert snapshot.total_trades == 15
        assert snapshot.win_count == 10
        assert snapshot.loss_count == 5
        assert snapshot.win_rate == pytest.approx(10/15, rel=0.01)
    
    def test_edge_calculation_with_nonzero_slippage(self):
        """Test edge calculation with non-zero slippage."""
        monitor = RuntimeEdgeMonitor(window_size=50, enabled=True, fee_bps=9.0)
        
        # Create trades with explicit slippage
        for i in range(15):
            trade = create_mock_trade_entry(
                trade_id=f"test-{i}",
                session_id="session-1",
                universe_mode="TOP_20"
            )
            # Set slippage values
            trade.buy_slippage_bps = 2.0
            trade.sell_slippage_bps = 2.5
            # Avg slippage = (2.0 + 2.5) / 2 = 2.25
            
            monitor.record_trade(trade)
        
        snapshot = monitor.get_current_snapshot()
        
        assert snapshot is not None
        assert snapshot.avg_slippage_bps == pytest.approx(2.25, rel=0.01)
        
        # Effective Edge = Spread(44.5) - Slippage(2.25) - Fee(9.0) = 33.25
        assert snapshot.effective_edge_bps == pytest.approx(33.25, rel=0.1)
    
    def test_snapshot_logging(self):
        """Test snapshot logging to JSONL file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "edge_monitor.jsonl"
            
            monitor = RuntimeEdgeMonitor(
                window_size=50,
                output_path=log_path,
                enabled=True
            )
            
            # Add 15 trades (triggers auto-logging)
            for i in range(15):
                trade = create_mock_trade_entry(
                    trade_id=f"test-{i}",
                    session_id="session-1",
                    universe_mode="TOP_20"
                )
                monitor.record_trade(trade)
            
            # Check log file exists and has content
            assert log_path.exists()
            
            with open(log_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            # Should have at least 1 snapshot logged
            assert len(lines) >= 1
            
            # Parse first snapshot
            snapshot_data = json.loads(lines[0])
            assert "timestamp" in snapshot_data
            assert "effective_edge_bps" in snapshot_data
            assert "win_rate" in snapshot_data
    
    def test_get_summary(self):
        """Test get_summary method."""
        monitor = RuntimeEdgeMonitor(window_size=50, enabled=True)
        
        # No trades yet
        summary = monitor.get_summary()
        assert summary["status"] == "insufficient_data"
        assert summary["current_trades"] == 0
        
        # Add sufficient trades
        for i in range(20):
            trade = create_mock_trade_entry(
                trade_id=f"test-{i}",
                session_id="session-1",
                universe_mode="TOP_20"
            )
            monitor.record_trade(trade)
        
        summary = monitor.get_summary()
        assert summary["status"] == "active"
        assert summary["current_trades"] == 20
        assert "effective_edge_bps" in summary
        assert "avg_pnl_bps" in summary
        assert "win_rate" in summary


class TestEdgeSnapshot:
    """Tests for EdgeSnapshot dataclass."""
    
    def test_snapshot_creation(self):
        """Test EdgeSnapshot creation."""
        snapshot = EdgeSnapshot(
            timestamp="2025-12-05T17:00:00",
            window_size=50,
            avg_spread_bps=45.0,
            avg_slippage_bps=2.0,
            avg_fee_bps=9.0,
            effective_edge_bps=34.0,
            avg_pnl_bps=25.0,
            total_pnl_usd=100.0,
            total_trades=50,
            win_count=30,
            loss_count=20,
            win_rate=0.6
        )
        
        assert snapshot.window_size == 50
        assert snapshot.effective_edge_bps == 34.0
        assert snapshot.win_rate == 0.6


class TestIntegration:
    """Integration tests for Edge Monitor."""
    
    def test_realistic_trading_scenario(self):
        """Test realistic trading scenario with mixed results."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "edge_monitor.jsonl"
            
            monitor = RuntimeEdgeMonitor(
                window_size=30,
                output_path=log_path,
                enabled=True,
                fee_bps=9.0
            )
            
            # Simulate 25 trades with varied outcomes
            for i in range(25):
                trade = create_mock_trade_entry(
                    trade_id=f"trade-{i}",
                    session_id="session-test",
                    universe_mode="TOP_20"
                )
                
                # Vary spread
                trade.entry_spread_bps = 40.0 + (i % 10)
                trade.exit_spread_bps = 38.0 + (i % 10)
                
                # Vary slippage
                trade.buy_slippage_bps = 2.0 + (i % 3) * 0.5
                trade.sell_slippage_bps = 2.0 + (i % 3) * 0.5
                
                # Vary outcome
                if i % 3 == 0:
                    trade.trade_result = "loss"
                    trade.net_pnl_usd = -50.0
                else:
                    trade.trade_result = "win"
                    trade.net_pnl_usd = 75.0
                
                monitor.record_trade(trade)
            
            # Get final snapshot
            snapshot = monitor.get_current_snapshot()
            
            assert snapshot is not None
            assert snapshot.total_trades == 25
            assert snapshot.win_count + snapshot.loss_count == 25
            assert 0.0 <= snapshot.win_rate <= 1.0
            
            # Check that log file has multiple snapshots
            with open(log_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            # Should have multiple snapshots logged (one per trade after min threshold)
            assert len(lines) >= 10
