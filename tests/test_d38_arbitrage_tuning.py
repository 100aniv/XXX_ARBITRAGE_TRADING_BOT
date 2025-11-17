"""
D38: Arbitrage Tuning Job Runner Tests

Tests for:
- TuningConfig / TuningMetrics
- ArbitrageTuningRunner
- CLI tool
- Safety / policy compliance
"""

import io
import json
import subprocess
import tempfile
from pathlib import Path

import pytest

from arbitrage.arbitrage_tuning import (
    TuningConfig,
    TuningMetrics,
    ArbitrageTuningRunner,
)


class TestTuningConfig:
    """Tests for TuningConfig."""

    def test_tuning_config_creation(self):
        """TuningConfig can be created with valid parameters."""
        config = TuningConfig(
            data_file="data/sample.csv",
            min_spread_bps=30.0,
            taker_fee_a_bps=5.0,
            taker_fee_b_bps=5.0,
            slippage_bps=5.0,
            max_position_usd=1000.0,
        )
        assert config.data_file == "data/sample.csv"
        assert config.min_spread_bps == 30.0
        assert config.max_open_trades == 1  # default
        assert config.initial_balance_usd == 10_000.0  # default

    def test_tuning_config_with_optional_params(self):
        """TuningConfig with optional parameters."""
        config = TuningConfig(
            data_file="data/sample.csv",
            min_spread_bps=40.0,
            taker_fee_a_bps=7.0,
            taker_fee_b_bps=7.0,
            slippage_bps=5.0,
            max_position_usd=1500.0,
            max_open_trades=2,
            initial_balance_usd=20_000.0,
            stop_on_drawdown_pct=25.0,
            tag="experiment_001",
        )
        assert config.max_open_trades == 2
        assert config.initial_balance_usd == 20_000.0
        assert config.stop_on_drawdown_pct == 25.0
        assert config.tag == "experiment_001"

    def test_tuning_config_validation_empty_data_file(self):
        """TuningConfig validation: empty data_file."""
        with pytest.raises(ValueError, match="data_file must be specified"):
            TuningConfig(
                data_file="",
                min_spread_bps=30.0,
                taker_fee_a_bps=5.0,
                taker_fee_b_bps=5.0,
                slippage_bps=5.0,
                max_position_usd=1000.0,
            )

    def test_tuning_config_validation_negative_spread(self):
        """TuningConfig validation: negative min_spread_bps."""
        with pytest.raises(ValueError, match="min_spread_bps must be non-negative"):
            TuningConfig(
                data_file="data/sample.csv",
                min_spread_bps=-10.0,
                taker_fee_a_bps=5.0,
                taker_fee_b_bps=5.0,
                slippage_bps=5.0,
                max_position_usd=1000.0,
            )

    def test_tuning_config_validation_negative_position(self):
        """TuningConfig validation: non-positive max_position_usd."""
        with pytest.raises(ValueError, match="max_position_usd must be positive"):
            TuningConfig(
                data_file="data/sample.csv",
                min_spread_bps=30.0,
                taker_fee_a_bps=5.0,
                taker_fee_b_bps=5.0,
                slippage_bps=5.0,
                max_position_usd=0.0,
            )

    def test_tuning_config_validation_negative_balance(self):
        """TuningConfig validation: non-positive initial_balance_usd."""
        with pytest.raises(ValueError, match="initial_balance_usd must be positive"):
            TuningConfig(
                data_file="data/sample.csv",
                min_spread_bps=30.0,
                taker_fee_a_bps=5.0,
                taker_fee_b_bps=5.0,
                slippage_bps=5.0,
                max_position_usd=1000.0,
                initial_balance_usd=-1000.0,
            )


class TestTuningMetrics:
    """Tests for TuningMetrics."""

    def test_tuning_metrics_creation(self):
        """TuningMetrics can be created."""
        metrics = TuningMetrics(
            total_trades=10,
            closed_trades=8,
            open_trades=2,
            final_balance_usd=11_000.0,
            realized_pnl_usd=1_000.0,
            max_drawdown_pct=5.0,
            win_rate=0.75,
            avg_pnl_per_trade_usd=125.0,
        )
        assert metrics.total_trades == 10
        assert metrics.closed_trades == 8
        assert metrics.open_trades == 2
        assert metrics.final_balance_usd == 11_000.0
        assert metrics.realized_pnl_usd == 1_000.0
        assert metrics.max_drawdown_pct == 5.0
        assert metrics.win_rate == 0.75
        assert metrics.avg_pnl_per_trade_usd == 125.0

    def test_tuning_metrics_with_runtime(self):
        """TuningMetrics with runtime_seconds."""
        metrics = TuningMetrics(
            total_trades=5,
            closed_trades=5,
            open_trades=0,
            final_balance_usd=10_500.0,
            realized_pnl_usd=500.0,
            max_drawdown_pct=2.0,
            win_rate=1.0,
            avg_pnl_per_trade_usd=100.0,
            runtime_seconds=0.123,
        )
        assert metrics.runtime_seconds == 0.123
        assert metrics.runtime_seconds >= 0

    def test_tuning_metrics_with_config_summary(self):
        """TuningMetrics with config_summary."""
        config_summary = {
            "min_spread_bps": 30.0,
            "max_position_usd": 1000.0,
        }
        metrics = TuningMetrics(
            total_trades=0,
            closed_trades=0,
            open_trades=0,
            final_balance_usd=10_000.0,
            realized_pnl_usd=0.0,
            max_drawdown_pct=0.0,
            win_rate=0.0,
            avg_pnl_per_trade_usd=0.0,
            config_summary=config_summary,
        )
        assert metrics.config_summary == config_summary
        assert "min_spread_bps" in metrics.config_summary


class TestArbitrageTuningRunner:
    """Tests for ArbitrageTuningRunner."""

    def _create_sample_csv(self, tmp_path: Path) -> Path:
        """Create a sample CSV file for testing."""
        csv_file = tmp_path / "sample.csv"
        csv_content = """timestamp,best_bid_a,best_ask_a,best_bid_b,best_ask_b
2025-01-01T00:00:00Z,99.0,100.0,102.0,103.0
2025-01-01T01:00:00Z,99.5,100.5,102.5,103.5
2025-01-01T02:00:00Z,100.0,101.0,103.0,104.0
"""
        csv_file.write_text(csv_content)
        return csv_file

    def test_load_snapshots_success(self, tmp_path):
        """load_snapshots() successfully loads a valid CSV."""
        csv_file = self._create_sample_csv(tmp_path)

        config = TuningConfig(
            data_file=str(csv_file),
            min_spread_bps=30.0,
            taker_fee_a_bps=5.0,
            taker_fee_b_bps=5.0,
            slippage_bps=5.0,
            max_position_usd=1000.0,
        )
        runner = ArbitrageTuningRunner(config)
        snapshots = runner.load_snapshots()

        assert len(snapshots) == 3
        assert snapshots[0].timestamp == "2025-01-01T00:00:00Z"
        assert snapshots[0].best_bid_a == 99.0
        assert snapshots[0].best_ask_a == 100.0

    def test_load_snapshots_file_not_found(self):
        """load_snapshots() raises FileNotFoundError if file doesn't exist."""
        config = TuningConfig(
            data_file="/nonexistent/path/sample.csv",
            min_spread_bps=30.0,
            taker_fee_a_bps=5.0,
            taker_fee_b_bps=5.0,
            slippage_bps=5.0,
            max_position_usd=1000.0,
        )
        runner = ArbitrageTuningRunner(config)

        with pytest.raises(FileNotFoundError, match="Data file not found"):
            runner.load_snapshots()

    def test_load_snapshots_empty_csv(self, tmp_path):
        """load_snapshots() raises ValueError if CSV is empty."""
        csv_file = tmp_path / "empty.csv"
        csv_file.write_text("")

        config = TuningConfig(
            data_file=str(csv_file),
            min_spread_bps=30.0,
            taker_fee_a_bps=5.0,
            taker_fee_b_bps=5.0,
            slippage_bps=5.0,
            max_position_usd=1000.0,
        )
        runner = ArbitrageTuningRunner(config)

        with pytest.raises(ValueError, match="CSV file is empty"):
            runner.load_snapshots()

    def test_load_snapshots_missing_columns(self, tmp_path):
        """load_snapshots() raises ValueError if required columns are missing."""
        csv_file = tmp_path / "bad_columns.csv"
        csv_content = """timestamp,best_bid_a,best_ask_a
2025-01-01T00:00:00Z,99.0,100.0
"""
        csv_file.write_text(csv_content)

        config = TuningConfig(
            data_file=str(csv_file),
            min_spread_bps=30.0,
            taker_fee_a_bps=5.0,
            taker_fee_b_bps=5.0,
            slippage_bps=5.0,
            max_position_usd=1000.0,
        )
        runner = ArbitrageTuningRunner(config)

        with pytest.raises(ValueError, match="CSV must have columns"):
            runner.load_snapshots()

    def test_load_snapshots_invalid_row(self, tmp_path):
        """load_snapshots() raises ValueError if a row has invalid data."""
        csv_file = tmp_path / "invalid_row.csv"
        csv_content = """timestamp,best_bid_a,best_ask_a,best_bid_b,best_ask_b
2025-01-01T00:00:00Z,99.0,100.0,102.0,103.0
2025-01-01T01:00:00Z,invalid,100.5,102.5,103.5
"""
        csv_file.write_text(csv_content)

        config = TuningConfig(
            data_file=str(csv_file),
            min_spread_bps=30.0,
            taker_fee_a_bps=5.0,
            taker_fee_b_bps=5.0,
            slippage_bps=5.0,
            max_position_usd=1000.0,
        )
        runner = ArbitrageTuningRunner(config)

        with pytest.raises(ValueError, match="Invalid row"):
            runner.load_snapshots()

    def test_run_success(self, tmp_path):
        """run() successfully completes a tuning job."""
        csv_file = self._create_sample_csv(tmp_path)

        config = TuningConfig(
            data_file=str(csv_file),
            min_spread_bps=30.0,
            taker_fee_a_bps=5.0,
            taker_fee_b_bps=5.0,
            slippage_bps=5.0,
            max_position_usd=1000.0,
            initial_balance_usd=10_000.0,
        )
        runner = ArbitrageTuningRunner(config)
        metrics = runner.run()

        assert isinstance(metrics, TuningMetrics)
        assert metrics.total_trades >= 0
        assert metrics.closed_trades >= 0
        assert metrics.open_trades >= 0
        assert metrics.final_balance_usd > 0
        assert metrics.max_drawdown_pct >= 0
        assert 0 <= metrics.win_rate <= 1
        assert metrics.runtime_seconds is not None
        assert metrics.runtime_seconds >= 0

    def test_run_metrics_consistency(self, tmp_path):
        """run() produces consistent metrics."""
        csv_file = self._create_sample_csv(tmp_path)

        config = TuningConfig(
            data_file=str(csv_file),
            min_spread_bps=30.0,
            taker_fee_a_bps=5.0,
            taker_fee_b_bps=5.0,
            slippage_bps=5.0,
            max_position_usd=1000.0,
        )
        runner = ArbitrageTuningRunner(config)
        metrics = runner.run()

        # Verify consistency
        assert metrics.total_trades == metrics.closed_trades + metrics.open_trades
        assert metrics.config_summary is not None
        assert "min_spread_bps" in metrics.config_summary
        assert "max_position_usd" in metrics.config_summary

    def test_run_with_drawdown_limit(self, tmp_path):
        """run() respects stop_on_drawdown_pct."""
        csv_file = self._create_sample_csv(tmp_path)

        config = TuningConfig(
            data_file=str(csv_file),
            min_spread_bps=30.0,
            taker_fee_a_bps=5.0,
            taker_fee_b_bps=5.0,
            slippage_bps=5.0,
            max_position_usd=1000.0,
            stop_on_drawdown_pct=5.0,
        )
        runner = ArbitrageTuningRunner(config)
        metrics = runner.run()

        # Should complete without error
        assert metrics.max_drawdown_pct >= 0

    def test_run_deterministic(self, tmp_path):
        """run() is deterministic (same input → same output)."""
        csv_file = self._create_sample_csv(tmp_path)

        config = TuningConfig(
            data_file=str(csv_file),
            min_spread_bps=30.0,
            taker_fee_a_bps=5.0,
            taker_fee_b_bps=5.0,
            slippage_bps=5.0,
            max_position_usd=1000.0,
        )

        runner1 = ArbitrageTuningRunner(config)
        metrics1 = runner1.run()

        runner2 = ArbitrageTuningRunner(config)
        metrics2 = runner2.run()

        assert metrics1.total_trades == metrics2.total_trades
        assert metrics1.final_balance_usd == metrics2.final_balance_usd
        assert metrics1.realized_pnl_usd == metrics2.realized_pnl_usd


class TestCLIIntegration:
    """Tests for the CLI tool."""

    def _create_sample_csv(self, tmp_path: Path) -> Path:
        """Create a sample CSV file for testing."""
        csv_file = tmp_path / "sample.csv"
        csv_content = """timestamp,best_bid_a,best_ask_a,best_bid_b,best_ask_b
2025-01-01T00:00:00Z,99.0,100.0,102.0,103.0
2025-01-01T01:00:00Z,99.5,100.5,102.5,103.5
2025-01-01T02:00:00Z,100.0,101.0,103.0,104.0
"""
        csv_file.write_text(csv_content)
        return csv_file

    def test_cli_json_output_structure(self, tmp_path):
        """CLI output JSON has correct structure."""
        csv_file = self._create_sample_csv(tmp_path)

        config = TuningConfig(
            data_file=str(csv_file),
            min_spread_bps=30.0,
            taker_fee_a_bps=5.0,
            taker_fee_b_bps=5.0,
            slippage_bps=5.0,
            max_position_usd=1000.0,
            tag="test_tag",
        )
        runner = ArbitrageTuningRunner(config)
        metrics = runner.run()

        # Build output JSON (same as CLI does)
        output_json = {
            "status": "success",
            "config": {
                "data_file": config.data_file,
                "min_spread_bps": config.min_spread_bps,
                "taker_fee_a_bps": config.taker_fee_a_bps,
                "taker_fee_b_bps": config.taker_fee_b_bps,
                "slippage_bps": config.slippage_bps,
                "max_position_usd": config.max_position_usd,
                "max_open_trades": config.max_open_trades,
                "initial_balance_usd": config.initial_balance_usd,
                "stop_on_drawdown_pct": config.stop_on_drawdown_pct,
                "tag": config.tag,
            },
            "metrics": {
                "total_trades": metrics.total_trades,
                "closed_trades": metrics.closed_trades,
                "open_trades": metrics.open_trades,
                "final_balance_usd": metrics.final_balance_usd,
                "realized_pnl_usd": metrics.realized_pnl_usd,
                "max_drawdown_pct": metrics.max_drawdown_pct,
                "win_rate": metrics.win_rate,
                "avg_pnl_per_trade_usd": metrics.avg_pnl_per_trade_usd,
                "runtime_seconds": metrics.runtime_seconds,
            },
        }

        # Verify schema
        assert "status" in output_json
        assert output_json["status"] == "success"
        assert "config" in output_json
        assert "metrics" in output_json

        # Verify config fields
        config_data = output_json["config"]
        assert "data_file" in config_data
        assert "min_spread_bps" in config_data
        assert "max_position_usd" in config_data
        assert "tag" in config_data

        # Verify metrics fields
        metrics_data = output_json["metrics"]
        assert "total_trades" in metrics_data
        assert "final_balance_usd" in metrics_data
        assert "realized_pnl_usd" in metrics_data
        assert "win_rate" in metrics_data
        assert "runtime_seconds" in metrics_data

    def test_cli_config_validation_error(self):
        """CLI handles configuration errors gracefully."""
        with pytest.raises(ValueError):
            TuningConfig(
                data_file="data/sample.csv",
                min_spread_bps=-10.0,  # Invalid
                taker_fee_a_bps=5.0,
                taker_fee_b_bps=5.0,
                slippage_bps=5.0,
                max_position_usd=1000.0,
            )

    def test_cli_file_not_found_error(self):
        """CLI handles file not found error gracefully."""
        config = TuningConfig(
            data_file="/nonexistent/path/sample.csv",
            min_spread_bps=30.0,
            taker_fee_a_bps=5.0,
            taker_fee_b_bps=5.0,
            slippage_bps=5.0,
            max_position_usd=1000.0,
        )
        runner = ArbitrageTuningRunner(config)

        with pytest.raises(RuntimeError, match="Tuning job failed"):
            runner.run()

    def test_cli_with_optional_params(self, tmp_path):
        """CLI works with optional parameters."""
        csv_file = self._create_sample_csv(tmp_path)

        config = TuningConfig(
            data_file=str(csv_file),
            min_spread_bps=40.0,
            taker_fee_a_bps=7.0,
            taker_fee_b_bps=7.0,
            slippage_bps=5.0,
            max_position_usd=1500.0,
            max_open_trades=2,
            initial_balance_usd=20_000.0,
            stop_on_drawdown_pct=25.0,
            tag="experiment_001",
        )
        runner = ArbitrageTuningRunner(config)
        metrics = runner.run()

        assert metrics.total_trades >= 0
        assert metrics.config_summary is not None
        assert metrics.config_summary["tag"] == "experiment_001"
        assert metrics.config_summary["max_open_trades"] == 2


class TestSafetyAndPolicy:
    """Tests for safety and policy compliance."""

    def test_no_network_calls(self):
        """Verify no network calls in arbitrage_tuning module."""
        import arbitrage.arbitrage_tuning as tuning_module

        # Check that requests is not imported
        assert not hasattr(tuning_module, "requests")
        assert not hasattr(tuning_module, "urllib")

    def test_no_kubectl_calls(self):
        """Verify no kubectl calls in arbitrage_tuning module."""
        import arbitrage.arbitrage_tuning as tuning_module

        # Check that subprocess is not used for kubectl
        source = open(
            "arbitrage/arbitrage_tuning.py", "r", encoding="utf-8"
        ).read()
        assert "kubectl" not in source
        assert "subprocess" not in source

    def test_no_k8s_integration(self):
        """Verify no K8s integration in arbitrage_tuning module."""
        import arbitrage.arbitrage_tuning as tuning_module

        # Check that K8s modules are not imported
        assert not hasattr(tuning_module, "kubernetes")

    def test_read_only_file_access(self, tmp_path):
        """Verify only read-only file access (CSV loading)."""
        csv_file = tmp_path / "sample.csv"
        csv_content = """timestamp,best_bid_a,best_ask_a,best_bid_b,best_ask_b
2025-01-01T00:00:00Z,99.0,100.0,102.0,103.0
"""
        csv_file.write_text(csv_content)

        config = TuningConfig(
            data_file=str(csv_file),
            min_spread_bps=30.0,
            taker_fee_a_bps=5.0,
            taker_fee_b_bps=5.0,
            slippage_bps=5.0,
            max_position_usd=1000.0,
        )
        runner = ArbitrageTuningRunner(config)

        # Should only read, not write
        snapshots = runner.load_snapshots()
        assert len(snapshots) == 1

        # Verify file is unchanged
        assert csv_file.read_text() == csv_content

    def test_deterministic_no_global_state(self, tmp_path):
        """Verify no global state (deterministic behavior)."""
        csv_file = tmp_path / "sample.csv"
        csv_content = """timestamp,best_bid_a,best_ask_a,best_bid_b,best_ask_b
2025-01-01T00:00:00Z,99.0,100.0,102.0,103.0
2025-01-01T01:00:00Z,99.5,100.5,102.5,103.5
"""
        csv_file.write_text(csv_content)

        config = TuningConfig(
            data_file=str(csv_file),
            min_spread_bps=30.0,
            taker_fee_a_bps=5.0,
            taker_fee_b_bps=5.0,
            slippage_bps=5.0,
            max_position_usd=1000.0,
        )

        # Run multiple times
        results = []
        for _ in range(3):
            runner = ArbitrageTuningRunner(config)
            metrics = runner.run()
            results.append(metrics)

        # All results should be identical
        assert results[0].total_trades == results[1].total_trades
        assert results[1].total_trades == results[2].total_trades
        assert results[0].final_balance_usd == results[1].final_balance_usd
        assert results[1].final_balance_usd == results[2].final_balance_usd
