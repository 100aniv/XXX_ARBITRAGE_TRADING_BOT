"""
D38: Arbitrage Tuning Job Runner

A single tuning job runner that:
- Takes one arbitrage configuration + one dataset
- Runs a backtest
- Computes stable metrics JSON
- Writes to file or stdout
- Is K8s Job-friendly (simple CLI, deterministic exit codes)

No external network calls, no K8s integration.
"""

import csv
import time
from dataclasses import dataclass, asdict, field
from typing import Dict, Any, Optional, List

from arbitrage.arbitrage_core import (
    ArbitrageConfig,
    ArbitrageEngine,
    OrderBookSnapshot,
)
from arbitrage.arbitrage_backtest import (
    BacktestConfig,
    ArbitrageBacktester,
    BacktestResult,
)


@dataclass
class TuningConfig:
    """Tuning job configuration: dataset + strategy + backtest params."""

    # Data / input
    data_file: str

    # Strategy parameters (mirror ArbitrageConfig + some extras)
    min_spread_bps: float
    taker_fee_a_bps: float
    taker_fee_b_bps: float
    slippage_bps: float
    max_position_usd: float
    max_open_trades: int = 1

    # Backtest parameters
    initial_balance_usd: float = 10_000.0
    stop_on_drawdown_pct: Optional[float] = None

    # Optional metadata (for tagging experiments)
    tag: Optional[str] = None
    extra: Optional[Dict[str, Any]] = field(default_factory=dict)

    def __post_init__(self):
        """Validate configuration."""
        if not self.data_file:
            raise ValueError("data_file must be specified")
        if self.min_spread_bps < 0:
            raise ValueError("min_spread_bps must be non-negative")
        if self.taker_fee_a_bps < 0:
            raise ValueError("taker_fee_a_bps must be non-negative")
        if self.taker_fee_b_bps < 0:
            raise ValueError("taker_fee_b_bps must be non-negative")
        if self.slippage_bps < 0:
            raise ValueError("slippage_bps must be non-negative")
        if self.max_position_usd <= 0:
            raise ValueError("max_position_usd must be positive")
        if self.initial_balance_usd <= 0:
            raise ValueError("initial_balance_usd must be positive")
        if self.max_open_trades < 1:
            raise ValueError("max_open_trades must be at least 1")
        if self.stop_on_drawdown_pct is not None and self.stop_on_drawdown_pct <= 0:
            raise ValueError("stop_on_drawdown_pct must be positive")


@dataclass
class TuningMetrics:
    """Metrics from a tuning job run."""

    # Core metrics
    total_trades: int
    closed_trades: int
    open_trades: int
    final_balance_usd: float
    realized_pnl_usd: float
    max_drawdown_pct: float
    win_rate: float
    avg_pnl_per_trade_usd: float

    # Optional extensions
    runtime_seconds: Optional[float] = None
    config_summary: Optional[Dict[str, Any]] = None


class ArbitrageTuningRunner:
    """Runs a single arbitrage tuning job."""

    def __init__(self, tuning_config: TuningConfig):
        """
        Initialize the tuning runner.

        Args:
            tuning_config: TuningConfig instance with all parameters.
        """
        self.tuning_config = tuning_config

    def load_snapshots(self) -> List[OrderBookSnapshot]:
        """
        Load snapshots from a CSV file.

        Expected CSV format:
        timestamp,best_bid_a,best_ask_a,best_bid_b,best_ask_b

        Returns:
            List of OrderBookSnapshot objects.

        Raises:
            FileNotFoundError: If data file does not exist.
            ValueError: If CSV format is invalid.
        """
        snapshots = []

        try:
            with open(self.tuning_config.data_file, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)

                if reader.fieldnames is None:
                    raise ValueError("CSV file is empty")

                expected_fields = {
                    "timestamp",
                    "best_bid_a",
                    "best_ask_a",
                    "best_bid_b",
                    "best_ask_b",
                }
                if not expected_fields.issubset(set(reader.fieldnames)):
                    raise ValueError(
                        f"CSV must have columns: {', '.join(expected_fields)}"
                    )

                for row_num, row in enumerate(reader, start=2):  # start=2 (header is 1)
                    try:
                        snapshot = OrderBookSnapshot(
                            timestamp=row["timestamp"],
                            best_bid_a=float(row["best_bid_a"]),
                            best_ask_a=float(row["best_ask_a"]),
                            best_bid_b=float(row["best_bid_b"]),
                            best_ask_b=float(row["best_ask_b"]),
                        )
                        snapshots.append(snapshot)
                    except (ValueError, KeyError) as e:
                        raise ValueError(
                            f"Invalid row {row_num}: {e}"
                        ) from e

        except FileNotFoundError as e:
            raise FileNotFoundError(
                f"Data file not found: {self.tuning_config.data_file}"
            ) from e

        if not snapshots:
            raise ValueError("No valid snapshots loaded from CSV file")

        return snapshots

    def run(self) -> TuningMetrics:
        """
        Run the tuning job.

        Steps:
        1. Load price snapshots from CSV.
        2. Build ArbitrageConfig and ArbitrageEngine.
        3. Build BacktestConfig and ArbitrageBacktester.
        4. Run backtest.
        5. Convert BacktestResult → TuningMetrics.
        6. Set runtime_seconds and config_summary.

        Returns:
            TuningMetrics object with results.

        Raises:
            FileNotFoundError: If data file not found.
            ValueError: If configuration or data is invalid.
        """
        start_time = time.time()

        try:
            # Step 1: Load snapshots
            snapshots = self.load_snapshots()

            # Step 2: Build ArbitrageConfig and ArbitrageEngine
            arbitrage_config = ArbitrageConfig(
                min_spread_bps=self.tuning_config.min_spread_bps,
                taker_fee_a_bps=self.tuning_config.taker_fee_a_bps,
                taker_fee_b_bps=self.tuning_config.taker_fee_b_bps,
                slippage_bps=self.tuning_config.slippage_bps,
                max_position_usd=self.tuning_config.max_position_usd,
                max_open_trades=self.tuning_config.max_open_trades,
            )
            engine = ArbitrageEngine(arbitrage_config)

            # Step 3: Build BacktestConfig and ArbitrageBacktester
            backtest_config = BacktestConfig(
                initial_balance_usd=self.tuning_config.initial_balance_usd,
                stop_on_drawdown_pct=self.tuning_config.stop_on_drawdown_pct,
            )
            backtester = ArbitrageBacktester(engine, backtest_config)

            # Step 4: Run backtest
            backtest_result = backtester.run(snapshots)

            # Step 5: Convert BacktestResult → TuningMetrics
            runtime_seconds = time.time() - start_time

            config_summary = {
                "data_file": self.tuning_config.data_file,
                "min_spread_bps": self.tuning_config.min_spread_bps,
                "taker_fee_a_bps": self.tuning_config.taker_fee_a_bps,
                "taker_fee_b_bps": self.tuning_config.taker_fee_b_bps,
                "slippage_bps": self.tuning_config.slippage_bps,
                "max_position_usd": self.tuning_config.max_position_usd,
                "max_open_trades": self.tuning_config.max_open_trades,
                "initial_balance_usd": self.tuning_config.initial_balance_usd,
                "stop_on_drawdown_pct": self.tuning_config.stop_on_drawdown_pct,
                "tag": self.tuning_config.tag,
                "snapshots_count": len(snapshots),
            }

            metrics = TuningMetrics(
                total_trades=backtest_result.total_trades,
                closed_trades=backtest_result.closed_trades,
                open_trades=backtest_result.open_trades,
                final_balance_usd=backtest_result.final_balance_usd,
                realized_pnl_usd=backtest_result.realized_pnl_usd,
                max_drawdown_pct=backtest_result.max_drawdown_pct,
                win_rate=backtest_result.win_rate,
                avg_pnl_per_trade_usd=backtest_result.avg_pnl_per_trade_usd,
                runtime_seconds=runtime_seconds,
                config_summary=config_summary,
            )

            return metrics

        except Exception as e:
            # Re-raise with context
            raise RuntimeError(f"Tuning job failed: {e}") from e
