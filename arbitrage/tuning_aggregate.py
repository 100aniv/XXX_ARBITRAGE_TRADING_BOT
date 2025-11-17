"""
D39: Arbitrage Tuning Results Aggregator

A module for aggregating multiple D38 result JSON files:
- Load results from a directory
- Filter by criteria (drawdown, min trades)
- Rank by performance metrics
- Offline-only, no external calls
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Any, List, Optional, Literal


@dataclass
class AggregatedJobResult:
    """A single aggregated job result."""
    job_id: str
    tag: Optional[str]
    config: Dict[str, Any]
    metrics: Dict[str, Any]
    status: Literal["success", "error"]


@dataclass
class AggregatedSummary:
    """Summary of aggregated results."""
    total_jobs: int
    success_jobs: int
    error_jobs: int
    top_by_pnl: List[AggregatedJobResult]
    filters: Dict[str, Any]


class TuningResultsAggregator:
    """Aggregator for D38 result JSON files."""

    def __init__(
        self,
        results_dir: str,
        max_results: int = 100,
        max_drawdown_pct: Optional[float] = None,
        min_trades: Optional[int] = None,
    ):
        """Initialize aggregator."""
        self.results_dir = Path(results_dir)
        self.max_results = max_results
        self.max_drawdown_pct = max_drawdown_pct
        self.min_trades = min_trades

    def load_results(self) -> List[AggregatedJobResult]:
        """
        Scan results_dir for *.json files (D38 outputs),
        load them, and convert to AggregatedJobResult.
        If parsing fails, mark status="error".
        """
        results = []

        if not self.results_dir.exists():
            return results

        # Find all JSON files recursively
        json_files = list(self.results_dir.glob("**/*.json"))

        for json_file in json_files:
            try:
                with open(json_file, "r", encoding="utf-8") as f:
                    data = json.load(f)

                # Extract fields
                status = data.get("status", "error")
                config = data.get("config", {})
                metrics = data.get("metrics", {})
                config_summary = data.get("config_summary", {})

                # Infer job_id and tag
                job_id = config_summary.get("job_id") or json_file.stem
                tag = config.get("tag")

                result = AggregatedJobResult(
                    job_id=job_id,
                    tag=tag,
                    config=config,
                    metrics=metrics,
                    status=status if status == "success" else "error",
                )
                results.append(result)

            except (json.JSONDecodeError, IOError, KeyError):
                # Mark as error but don't crash
                result = AggregatedJobResult(
                    job_id=json_file.stem,
                    tag=None,
                    config={},
                    metrics={},
                    status="error",
                )
                results.append(result)

        return results

    def summarize(self) -> AggregatedSummary:
        """
        - Load all results.
        - Filter by max_drawdown_pct (if set).
        - Filter by min_trades (if set).
        - Rank by realized_pnl_usd (descending).
        - Pick up to max_results for top_by_pnl.
        - Return AggregatedSummary with filter criteria included.
        """
        all_results = self.load_results()

        # Count totals
        total_jobs = len(all_results)
        success_jobs = sum(1 for r in all_results if r.status == "success")
        error_jobs = total_jobs - success_jobs

        # Filter results
        filtered_results = []
        for result in all_results:
            if result.status != "success":
                continue

            metrics = result.metrics

            # Check max_drawdown_pct filter
            if self.max_drawdown_pct is not None:
                max_dd = metrics.get("max_drawdown_pct", 100.0)
                if max_dd > self.max_drawdown_pct:
                    continue

            # Check min_trades filter
            if self.min_trades is not None:
                total_trades = metrics.get("total_trades", 0)
                if total_trades < self.min_trades:
                    continue

            filtered_results.append(result)

        # Sort by realized_pnl_usd (descending)
        filtered_results.sort(
            key=lambda r: r.metrics.get("realized_pnl_usd", 0.0),
            reverse=True,
        )

        # Limit to max_results
        top_results = filtered_results[: self.max_results]

        # Build filters dict
        filters = {}
        if self.max_drawdown_pct is not None:
            filters["max_drawdown_pct"] = self.max_drawdown_pct
        if self.min_trades is not None:
            filters["min_trades"] = self.min_trades

        return AggregatedSummary(
            total_jobs=total_jobs,
            success_jobs=success_jobs,
            error_jobs=error_jobs,
            top_by_pnl=top_results,
            filters=filters,
        )
