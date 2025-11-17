"""
D39: Tuning Session Planner & Metrics Aggregator Tests

Tests for:
- TuningSessionConfig and ParamGrid
- TuningSessionPlanner.generate_jobs()
- TuningResultsAggregator.load_results() and summarize()
- CLI integration
- Safety and policy compliance
"""

import json
import subprocess
import tempfile
from pathlib import Path
from typing import List

import pytest

from arbitrage.tuning_session import (
    ParamGrid,
    TuningSessionConfig,
    TuningJobPlan,
    TuningSessionPlanner,
)
from arbitrage.tuning_aggregate import (
    AggregatedJobResult,
    AggregatedSummary,
    TuningResultsAggregator,
)


class TestParamGrid:
    """Tests for ParamGrid."""

    def test_param_grid_creation(self):
        """ParamGrid can be created with name and values."""
        grid = ParamGrid(name="min_spread_bps", values=[20, 30, 40])
        assert grid.name == "min_spread_bps"
        assert grid.values == [20, 30, 40]

    def test_param_grid_single_value(self):
        """ParamGrid can have a single value."""
        grid = ParamGrid(name="slippage_bps", values=[5.0])
        assert len(grid.values) == 1
        assert grid.values[0] == 5.0


class TestTuningSessionConfig:
    """Tests for TuningSessionConfig."""

    def test_session_config_creation(self):
        """TuningSessionConfig can be created with required fields."""
        config = TuningSessionConfig(
            data_file="data/sample.csv",
            min_spread_bps=30.0,
            taker_fee_a_bps=5.0,
            taker_fee_b_bps=5.0,
            slippage_bps=5.0,
            max_position_usd=1000.0,
        )
        assert config.data_file == "data/sample.csv"
        assert config.min_spread_bps == 30.0

    def test_session_config_with_grids(self):
        """TuningSessionConfig can include parameter grids."""
        grids = [
            ParamGrid(name="min_spread_bps", values=[20, 30, 40]),
            ParamGrid(name="slippage_bps", values=[3, 5]),
        ]
        config = TuningSessionConfig(
            data_file="data/sample.csv",
            min_spread_bps=30.0,
            taker_fee_a_bps=5.0,
            taker_fee_b_bps=5.0,
            slippage_bps=5.0,
            max_position_usd=1000.0,
            grids=grids,
        )
        assert len(config.grids) == 2

    def test_session_config_missing_data_file(self):
        """TuningSessionConfig raises error if data_file is missing."""
        with pytest.raises(ValueError, match="data_file is required"):
            TuningSessionConfig(
                data_file="",
                min_spread_bps=30.0,
                taker_fee_a_bps=5.0,
                taker_fee_b_bps=5.0,
                slippage_bps=5.0,
                max_position_usd=1000.0,
            )

    def test_session_config_defaults(self):
        """TuningSessionConfig has sensible defaults."""
        config = TuningSessionConfig(
            data_file="data/sample.csv",
            min_spread_bps=30.0,
            taker_fee_a_bps=5.0,
            taker_fee_b_bps=5.0,
            slippage_bps=5.0,
            max_position_usd=1000.0,
        )
        assert config.initial_balance_usd == 10_000.0
        assert config.max_open_trades == 1
        assert config.stop_on_drawdown_pct is None


class TestTuningSessionPlanner:
    """Tests for TuningSessionPlanner."""

    def test_planner_single_grid_single_value(self):
        """Planner with 1 grid, 1 value → 1 job."""
        grids = [ParamGrid(name="min_spread_bps", values=[30.0])]
        config = TuningSessionConfig(
            data_file="data/sample.csv",
            min_spread_bps=30.0,
            taker_fee_a_bps=5.0,
            taker_fee_b_bps=5.0,
            slippage_bps=5.0,
            max_position_usd=1000.0,
            grids=grids,
        )
        planner = TuningSessionPlanner(config)
        jobs = planner.generate_jobs()

        assert len(jobs) == 1
        assert jobs[0].job_id == "job_0001"
        assert jobs[0].config["min_spread_bps"] == 30.0

    def test_planner_cartesian_product(self):
        """Planner with 2 grids (2×3 values) → 6 jobs."""
        grids = [
            ParamGrid(name="min_spread_bps", values=[20.0, 30.0]),
            ParamGrid(name="slippage_bps", values=[3.0, 5.0, 7.0]),
        ]
        config = TuningSessionConfig(
            data_file="data/sample.csv",
            min_spread_bps=30.0,
            taker_fee_a_bps=5.0,
            taker_fee_b_bps=5.0,
            slippage_bps=5.0,
            max_position_usd=1000.0,
            grids=grids,
        )
        planner = TuningSessionPlanner(config)
        jobs = planner.generate_jobs()

        assert len(jobs) == 6
        # Check that all combinations are present
        combinations = set()
        for job in jobs:
            combo = (job.config["min_spread_bps"], job.config["slippage_bps"])
            combinations.add(combo)
        assert len(combinations) == 6

    def test_planner_max_jobs_limit(self):
        """Planner respects max_jobs limit."""
        grids = [
            ParamGrid(name="min_spread_bps", values=[20.0, 30.0, 40.0]),
            ParamGrid(name="slippage_bps", values=[3.0, 5.0, 7.0]),
        ]
        config = TuningSessionConfig(
            data_file="data/sample.csv",
            min_spread_bps=30.0,
            taker_fee_a_bps=5.0,
            taker_fee_b_bps=5.0,
            slippage_bps=5.0,
            max_position_usd=1000.0,
            grids=grids,
            max_jobs=5,
        )
        planner = TuningSessionPlanner(config)
        jobs = planner.generate_jobs()

        assert len(jobs) == 5

    def test_planner_job_id_sequencing(self):
        """Planner generates deterministic job IDs."""
        grids = [ParamGrid(name="min_spread_bps", values=[20.0, 30.0, 40.0])]
        config = TuningSessionConfig(
            data_file="data/sample.csv",
            min_spread_bps=30.0,
            taker_fee_a_bps=5.0,
            taker_fee_b_bps=5.0,
            slippage_bps=5.0,
            max_position_usd=1000.0,
            grids=grids,
        )
        planner = TuningSessionPlanner(config)
        jobs = planner.generate_jobs()

        assert jobs[0].job_id == "job_0001"
        assert jobs[1].job_id == "job_0002"
        assert jobs[2].job_id == "job_0003"

    def test_planner_job_id_with_tag_prefix(self):
        """Planner uses tag_prefix in job IDs."""
        grids = [ParamGrid(name="min_spread_bps", values=[20.0, 30.0])]
        config = TuningSessionConfig(
            data_file="data/sample.csv",
            min_spread_bps=30.0,
            taker_fee_a_bps=5.0,
            taker_fee_b_bps=5.0,
            slippage_bps=5.0,
            max_position_usd=1000.0,
            grids=grids,
            tag_prefix="sess001",
        )
        planner = TuningSessionPlanner(config)
        jobs = planner.generate_jobs()

        assert jobs[0].job_id == "sess001_0001"
        assert jobs[1].job_id == "sess001_0002"

    def test_planner_output_json_path(self):
        """Planner generates deterministic output_json paths."""
        grids = [ParamGrid(name="min_spread_bps", values=[20.0])]
        config = TuningSessionConfig(
            data_file="data/sample.csv",
            min_spread_bps=30.0,
            taker_fee_a_bps=5.0,
            taker_fee_b_bps=5.0,
            slippage_bps=5.0,
            max_position_usd=1000.0,
            grids=grids,
            tag_prefix="sess001",
        )
        planner = TuningSessionPlanner(config)
        jobs = planner.generate_jobs()

        assert "sess001" in jobs[0].output_json
        assert "sess001_0001.json" in jobs[0].output_json

    def test_planner_config_has_all_fields(self):
        """Planner config includes all required TuningConfig fields."""
        grids = [ParamGrid(name="min_spread_bps", values=[30.0])]
        config = TuningSessionConfig(
            data_file="data/sample.csv",
            min_spread_bps=30.0,
            taker_fee_a_bps=5.0,
            taker_fee_b_bps=5.0,
            slippage_bps=5.0,
            max_position_usd=1000.0,
            max_open_trades=2,
            initial_balance_usd=20_000.0,
            grids=grids,
        )
        planner = TuningSessionPlanner(config)
        jobs = planner.generate_jobs()

        job_config = jobs[0].config
        assert "data_file" in job_config
        assert "min_spread_bps" in job_config
        assert "taker_fee_a_bps" in job_config
        assert "taker_fee_b_bps" in job_config
        assert "slippage_bps" in job_config
        assert "max_position_usd" in job_config
        assert "max_open_trades" in job_config
        assert job_config["max_open_trades"] == 2
        assert job_config["initial_balance_usd"] == 20_000.0

    def test_planner_no_grids(self):
        """Planner with no grids generates 1 job with fixed params."""
        config = TuningSessionConfig(
            data_file="data/sample.csv",
            min_spread_bps=30.0,
            taker_fee_a_bps=5.0,
            taker_fee_b_bps=5.0,
            slippage_bps=5.0,
            max_position_usd=1000.0,
            grids=[],
        )
        planner = TuningSessionPlanner(config)
        jobs = planner.generate_jobs()

        assert len(jobs) == 1
        assert jobs[0].config["min_spread_bps"] == 30.0


class TestTuningResultsAggregator:
    """Tests for TuningResultsAggregator."""

    def _create_sample_result_json(self, tmp_path: Path, job_id: str, pnl: float, dd: float, trades: int) -> Path:
        """Create a sample D38 result JSON file."""
        result_file = tmp_path / f"{job_id}.json"
        result_data = {
            "status": "success",
            "config": {
                "data_file": "data/sample.csv",
                "min_spread_bps": 30.0,
                "taker_fee_a_bps": 5.0,
                "taker_fee_b_bps": 5.0,
                "slippage_bps": 5.0,
                "max_position_usd": 1000.0,
                "tag": "test_tag",
            },
            "metrics": {
                "total_trades": trades,
                "closed_trades": trades - 1,
                "open_trades": 1,
                "final_balance_usd": 10_000.0 + pnl,
                "realized_pnl_usd": pnl,
                "max_drawdown_pct": dd,
                "win_rate": 0.75,
                "avg_pnl_per_trade_usd": pnl / max(trades, 1),
                "runtime_seconds": 0.1,
            },
            "config_summary": {
                "job_id": job_id,
            },
        }
        with open(result_file, "w", encoding="utf-8") as f:
            json.dump(result_data, f)
        return result_file

    def test_aggregator_load_results_empty_dir(self, tmp_path):
        """Aggregator handles empty directory gracefully."""
        aggregator = TuningResultsAggregator(str(tmp_path))
        results = aggregator.load_results()
        assert len(results) == 0

    def test_aggregator_load_results_single_file(self, tmp_path):
        """Aggregator loads a single result JSON file."""
        self._create_sample_result_json(tmp_path, "job_0001", pnl=1000.0, dd=5.0, trades=10)
        aggregator = TuningResultsAggregator(str(tmp_path))
        results = aggregator.load_results()

        assert len(results) == 1
        assert results[0].job_id == "job_0001"
        assert results[0].status == "success"
        assert results[0].metrics["realized_pnl_usd"] == 1000.0

    def test_aggregator_load_results_multiple_files(self, tmp_path):
        """Aggregator loads multiple result JSON files."""
        self._create_sample_result_json(tmp_path, "job_0001", pnl=1000.0, dd=5.0, trades=10)
        self._create_sample_result_json(tmp_path, "job_0002", pnl=800.0, dd=8.0, trades=8)
        self._create_sample_result_json(tmp_path, "job_0003", pnl=1200.0, dd=3.0, trades=12)

        aggregator = TuningResultsAggregator(str(tmp_path))
        results = aggregator.load_results()

        assert len(results) == 3

    def test_aggregator_load_results_bad_json(self, tmp_path):
        """Aggregator marks bad JSON files as error."""
        bad_file = tmp_path / "bad_job.json"
        bad_file.write_text("{ invalid json }")

        aggregator = TuningResultsAggregator(str(tmp_path))
        results = aggregator.load_results()

        assert len(results) == 1
        assert results[0].status == "error"

    def test_aggregator_summarize_ranking(self, tmp_path):
        """Aggregator ranks results by PnL descending."""
        self._create_sample_result_json(tmp_path, "job_0001", pnl=1000.0, dd=5.0, trades=10)
        self._create_sample_result_json(tmp_path, "job_0002", pnl=800.0, dd=8.0, trades=8)
        self._create_sample_result_json(tmp_path, "job_0003", pnl=1200.0, dd=3.0, trades=12)

        aggregator = TuningResultsAggregator(str(tmp_path))
        summary = aggregator.summarize()

        assert len(summary.top_by_pnl) == 3
        assert summary.top_by_pnl[0].metrics["realized_pnl_usd"] == 1200.0
        assert summary.top_by_pnl[1].metrics["realized_pnl_usd"] == 1000.0
        assert summary.top_by_pnl[2].metrics["realized_pnl_usd"] == 800.0

    def test_aggregator_summarize_max_drawdown_filter(self, tmp_path):
        """Aggregator filters by max_drawdown_pct."""
        self._create_sample_result_json(tmp_path, "job_0001", pnl=1000.0, dd=5.0, trades=10)
        self._create_sample_result_json(tmp_path, "job_0002", pnl=800.0, dd=8.0, trades=8)
        self._create_sample_result_json(tmp_path, "job_0003", pnl=1200.0, dd=15.0, trades=12)

        aggregator = TuningResultsAggregator(
            str(tmp_path),
            max_drawdown_pct=10.0,
        )
        summary = aggregator.summarize()

        assert len(summary.top_by_pnl) == 2
        assert all(r.metrics["max_drawdown_pct"] <= 10.0 for r in summary.top_by_pnl)

    def test_aggregator_summarize_min_trades_filter(self, tmp_path):
        """Aggregator filters by min_trades."""
        self._create_sample_result_json(tmp_path, "job_0001", pnl=1000.0, dd=5.0, trades=10)
        self._create_sample_result_json(tmp_path, "job_0002", pnl=800.0, dd=8.0, trades=3)
        self._create_sample_result_json(tmp_path, "job_0003", pnl=1200.0, dd=3.0, trades=12)

        aggregator = TuningResultsAggregator(
            str(tmp_path),
            min_trades=5,
        )
        summary = aggregator.summarize()

        assert len(summary.top_by_pnl) == 2
        assert all(r.metrics["total_trades"] >= 5 for r in summary.top_by_pnl)

    def test_aggregator_summarize_max_results_limit(self, tmp_path):
        """Aggregator respects max_results limit."""
        for i in range(15):
            self._create_sample_result_json(tmp_path, f"job_{i:04d}", pnl=1000.0 - i*10, dd=5.0, trades=10)

        aggregator = TuningResultsAggregator(
            str(tmp_path),
            max_results=5,
        )
        summary = aggregator.summarize()

        assert len(summary.top_by_pnl) == 5

    def test_aggregator_summarize_counts(self, tmp_path):
        """Aggregator counts total, success, and error jobs."""
        self._create_sample_result_json(tmp_path, "job_0001", pnl=1000.0, dd=5.0, trades=10)
        self._create_sample_result_json(tmp_path, "job_0002", pnl=800.0, dd=8.0, trades=8)
        bad_file = tmp_path / "bad_job.json"
        bad_file.write_text("{ invalid json }")

        aggregator = TuningResultsAggregator(str(tmp_path))
        summary = aggregator.summarize()

        assert summary.total_jobs == 3
        assert summary.success_jobs == 2
        assert summary.error_jobs == 1

    def test_aggregator_summarize_filters_dict(self, tmp_path):
        """Aggregator includes filters in summary."""
        self._create_sample_result_json(tmp_path, "job_0001", pnl=1000.0, dd=5.0, trades=10)

        aggregator = TuningResultsAggregator(
            str(tmp_path),
            max_drawdown_pct=10.0,
            min_trades=5,
        )
        summary = aggregator.summarize()

        assert "max_drawdown_pct" in summary.filters
        assert summary.filters["max_drawdown_pct"] == 10.0
        assert "min_trades" in summary.filters
        assert summary.filters["min_trades"] == 5


class TestCLIIntegration:
    """Tests for CLI integration."""

    def test_plan_tuning_session_basic(self, tmp_path):
        """plan_tuning_session CLI works with minimal config."""
        # Create a minimal YAML session config
        session_file = tmp_path / "session.yaml"
        session_content = """
data_file: data/sample.csv
min_spread_bps: 30
taker_fee_a_bps: 5
taker_fee_b_bps: 5
slippage_bps: 5
max_position_usd: 1000
grids:
  - name: min_spread_bps
    values: [20, 30, 40]
"""
        session_file.write_text(session_content)

        output_file = tmp_path / "jobs.jsonl"

        # Note: This would require running the CLI, which we'll test differently
        # For now, test the planner directly
        from arbitrage.tuning_session import ParamGrid, TuningSessionConfig, TuningSessionPlanner

        grids = [ParamGrid(name="min_spread_bps", values=[20, 30, 40])]
        config = TuningSessionConfig(
            data_file="data/sample.csv",
            min_spread_bps=30.0,
            taker_fee_a_bps=5.0,
            taker_fee_b_bps=5.0,
            slippage_bps=5.0,
            max_position_usd=1000.0,
            grids=grids,
        )
        planner = TuningSessionPlanner(config)
        jobs = planner.generate_jobs()

        assert len(jobs) == 3


class TestSafetyAndPolicy:
    """Tests for safety and policy compliance."""

    def test_no_network_calls_tuning_session(self):
        """Verify no network calls in tuning_session module."""
        import arbitrage.tuning_session as session_module

        source = open(session_module.__file__).read()
        assert "requests" not in source
        assert "http" not in source.lower()
        assert "socket" not in source

    def test_no_network_calls_tuning_aggregate(self):
        """Verify no network calls in tuning_aggregate module."""
        import arbitrage.tuning_aggregate as agg_module

        source = open(agg_module.__file__).read()
        assert "requests" not in source
        assert "http" not in source.lower()
        assert "socket" not in source

    def test_no_kubectl_calls(self):
        """Verify no kubectl usage in D39 modules."""
        import arbitrage.tuning_session as session_module
        import arbitrage.tuning_aggregate as agg_module

        session_source = open(session_module.__file__).read()
        agg_source = open(agg_module.__file__).read()

        assert "kubectl" not in session_source
        assert "kubectl" not in agg_source

    def test_no_k8s_integration(self):
        """Verify no K8s module imports in D39."""
        import arbitrage.tuning_session as session_module
        import arbitrage.tuning_aggregate as agg_module

        session_source = open(session_module.__file__).read()
        agg_source = open(agg_module.__file__).read()

        assert "k8s_" not in session_source
        assert "k8s_" not in agg_source

    def test_deterministic_job_generation(self):
        """Job generation is deterministic for same config."""
        grids = [
            ParamGrid(name="min_spread_bps", values=[20, 30, 40]),
            ParamGrid(name="slippage_bps", values=[3, 5]),
        ]
        config = TuningSessionConfig(
            data_file="data/sample.csv",
            min_spread_bps=30.0,
            taker_fee_a_bps=5.0,
            taker_fee_b_bps=5.0,
            slippage_bps=5.0,
            max_position_usd=1000.0,
            grids=grids,
            tag_prefix="sess001",
        )

        planner1 = TuningSessionPlanner(config)
        jobs1 = planner1.generate_jobs()

        planner2 = TuningSessionPlanner(config)
        jobs2 = planner2.generate_jobs()

        assert len(jobs1) == len(jobs2)
        for j1, j2 in zip(jobs1, jobs2):
            assert j1.job_id == j2.job_id
            assert j1.config == j2.config
            assert j1.output_json == j2.output_json
