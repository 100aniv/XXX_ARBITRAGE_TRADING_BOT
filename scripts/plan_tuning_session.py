"""
D39: Plan Tuning Session CLI

CLI to generate a job plan file (JSONL) from a session spec (YAML or JSON).

Usage:
    python -m scripts.plan_tuning_session \
      --session-file configs/tuning/session001.yaml \
      --output-jobs-file outputs/tuning/session001_jobs.jsonl

Exit codes:
    0: Success
    1: Invalid session file or config
    2: Unexpected runtime error
"""

import argparse
import json
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None

from arbitrage.tuning_session import (
    TuningSessionConfig,
    ParamGrid,
    TuningSessionPlanner,
)


def load_session_config(session_file: str) -> TuningSessionConfig:
    """Load session config from YAML or JSON file."""
    session_path = Path(session_file)

    if not session_path.exists():
        raise FileNotFoundError(f"Session file not found: {session_file}")

    with open(session_path, "r", encoding="utf-8") as f:
        if session_path.suffix.lower() in [".yaml", ".yml"]:
            if yaml is None:
                raise ImportError("PyYAML is required for YAML files")
            data = yaml.safe_load(f)
        elif session_path.suffix.lower() == ".json":
            data = json.load(f)
        else:
            raise ValueError(f"Unsupported file format: {session_path.suffix}")

    # Extract fields
    data_file = data.get("data_file")
    if not data_file:
        raise ValueError("data_file is required in session config")

    # Fixed parameters
    fixed = data.get("fixed", {})
    min_spread_bps = fixed.get("min_spread_bps") or data.get("min_spread_bps")
    taker_fee_a_bps = fixed.get("taker_fee_a_bps") or data.get("taker_fee_a_bps")
    taker_fee_b_bps = fixed.get("taker_fee_b_bps") or data.get("taker_fee_b_bps")
    slippage_bps = fixed.get("slippage_bps") or data.get("slippage_bps")
    max_position_usd = fixed.get("max_position_usd") or data.get("max_position_usd")
    max_open_trades = fixed.get("max_open_trades") or data.get("max_open_trades", 1)
    initial_balance_usd = fixed.get("initial_balance_usd") or data.get(
        "initial_balance_usd", 10_000.0
    )
    stop_on_drawdown_pct = fixed.get("stop_on_drawdown_pct") or data.get(
        "stop_on_drawdown_pct"
    )

    # Parameter grids
    grids_data = data.get("grids", [])
    grids = [ParamGrid(name=g["name"], values=g["values"]) for g in grids_data]

    # Optional controls
    max_jobs = data.get("max_jobs")
    tag_prefix = data.get("tag_prefix")

    # Build config
    config = TuningSessionConfig(
        data_file=data_file,
        min_spread_bps=min_spread_bps,
        taker_fee_a_bps=taker_fee_a_bps,
        taker_fee_b_bps=taker_fee_b_bps,
        slippage_bps=slippage_bps,
        max_position_usd=max_position_usd,
        max_open_trades=max_open_trades,
        initial_balance_usd=initial_balance_usd,
        stop_on_drawdown_pct=stop_on_drawdown_pct,
        grids=grids,
        max_jobs=max_jobs,
        tag_prefix=tag_prefix,
    )

    return config


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Generate a job plan file (JSONL) from a tuning session spec."
    )

    parser.add_argument(
        "--session-file",
        required=True,
        help="Path to session spec file (YAML or JSON)",
    )
    parser.add_argument(
        "--output-jobs-file",
        required=True,
        help="Path to output JSONL file (one job plan per line)",
    )

    args = parser.parse_args()

    try:
        # Load session config
        session_config = load_session_config(args.session_file)

        # Generate job plans
        planner = TuningSessionPlanner(session_config)
        jobs = planner.generate_jobs()

        # Write JSONL
        output_path = Path(args.output_jobs_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w", encoding="utf-8") as f:
            for job in jobs:
                job_dict = {
                    "job_id": job.job_id,
                    "config": job.config,
                    "output_json": job.output_json,
                }
                f.write(json.dumps(job_dict) + "\n")

        print(
            f"[D39_PLAN] Generated {len(jobs)} job plans to: {output_path}",
            file=sys.stderr,
        )

        return 0

    except (ValueError, FileNotFoundError) as e:
        print(f"[D39_PLAN] ERROR: {e}", file=sys.stderr)
        return 1

    except Exception as e:
        print(f"[D39_PLAN] FATAL: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
