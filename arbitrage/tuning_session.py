"""
D39: Arbitrage Tuning Session Planner

A module for planning large-scale tuning sessions:
- Define parameter grids for sweep
- Generate job plans (cartesian product of parameters)
- Deterministic, offline-only, no external calls
"""

from dataclasses import dataclass, field, asdict
from typing import Dict, Any, List, Optional, Literal
from itertools import product
import uuid


@dataclass
class ParamGrid:
    """Discrete values for one parameter."""
    name: str
    values: List[float]  # Can be int or float


@dataclass
class TuningSessionConfig:
    """Configuration for a tuning session (grid sweep)."""
    data_file: str

    # Fixed parameters applied to all jobs (if not overridden in job-specific config)
    min_spread_bps: Optional[float] = None
    taker_fee_a_bps: Optional[float] = None
    taker_fee_b_bps: Optional[float] = None
    slippage_bps: Optional[float] = None
    max_position_usd: Optional[float] = None
    max_open_trades: Optional[int] = 1
    initial_balance_usd: float = 10_000.0
    stop_on_drawdown_pct: Optional[float] = None

    # Parameter grids (for sweep)
    grids: List[ParamGrid] = field(default_factory=list)

    # Optional controls
    max_jobs: Optional[int] = None   # Cap number of combinations
    tag_prefix: Optional[str] = None # Tag prefix for each job

    def __post_init__(self):
        """Validate session config."""
        if not self.data_file:
            raise ValueError("data_file is required")
        if self.grids is None:
            self.grids = []


@dataclass
class TuningJobPlan:
    """A single job plan (flattened representation)."""
    job_id: str              # Unique ID (e.g., "sess001_0001")
    config: Dict[str, Any]   # Dict matching TuningConfig fields
    output_json: str         # Suggested output path for this job


class TuningSessionPlanner:
    """Planner for generating job plans from a session config."""

    def __init__(self, session_config: TuningSessionConfig):
        """Initialize planner with session config."""
        self.session_config = session_config

    def generate_jobs(self) -> List[TuningJobPlan]:
        """
        Generate a list of job plans (cartesian product over grids).

        Steps:
        1. Combine all ParamGrid values (cartesian product).
        2. Apply fixed parameters from TuningSessionConfig.
        3. Add data_file to each config.
        4. Respect max_jobs if set (truncate in deterministic order).
        5. Generate job_id and output_json for each plan.
        """
        # Collect grid names and values
        grid_names = [g.name for g in self.session_config.grids]
        grid_values = [g.values for g in self.session_config.grids]

        # Generate cartesian product
        if not grid_values:
            # No grids: single job with all fixed parameters
            combinations = [{}]
        else:
            combinations = [
                dict(zip(grid_names, values))
                for values in product(*grid_values)
            ]

        # Apply max_jobs limit (deterministic truncation)
        if self.session_config.max_jobs is not None:
            combinations = combinations[: self.session_config.max_jobs]

        # Build job plans
        jobs = []
        for idx, combo in enumerate(combinations):
            job_id = self._generate_job_id(idx)
            config = self._build_config(combo)
            output_json = self._generate_output_path(job_id)

            job_plan = TuningJobPlan(
                job_id=job_id,
                config=config,
                output_json=output_json,
            )
            jobs.append(job_plan)

        return jobs

    def _generate_job_id(self, idx: int) -> str:
        """Generate deterministic job ID."""
        if self.session_config.tag_prefix:
            return f"{self.session_config.tag_prefix}_{idx+1:04d}"
        else:
            return f"job_{idx+1:04d}"

    def _build_config(self, grid_combo: Dict[str, Any]) -> Dict[str, Any]:
        """Build config dict for a single job."""
        config = {
            "data_file": self.session_config.data_file,
            "initial_balance_usd": self.session_config.initial_balance_usd,
            "max_open_trades": self.session_config.max_open_trades,
        }

        # Add fixed parameters (if not None)
        if self.session_config.min_spread_bps is not None:
            config["min_spread_bps"] = self.session_config.min_spread_bps
        if self.session_config.taker_fee_a_bps is not None:
            config["taker_fee_a_bps"] = self.session_config.taker_fee_a_bps
        if self.session_config.taker_fee_b_bps is not None:
            config["taker_fee_b_bps"] = self.session_config.taker_fee_b_bps
        if self.session_config.slippage_bps is not None:
            config["slippage_bps"] = self.session_config.slippage_bps
        if self.session_config.max_position_usd is not None:
            config["max_position_usd"] = self.session_config.max_position_usd
        if self.session_config.stop_on_drawdown_pct is not None:
            config["stop_on_drawdown_pct"] = self.session_config.stop_on_drawdown_pct

        # Override with grid values
        config.update(grid_combo)

        # Add tag if prefix is set
        if self.session_config.tag_prefix:
            config["tag"] = self.session_config.tag_prefix

        return config

    def _generate_output_path(self, job_id: str) -> str:
        """Generate output JSON path for a job."""
        if self.session_config.tag_prefix:
            return f"outputs/tuning/{self.session_config.tag_prefix}/{job_id}.json"
        else:
            return f"outputs/tuning/{job_id}.json"
