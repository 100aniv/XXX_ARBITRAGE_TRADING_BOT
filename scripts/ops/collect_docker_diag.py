#!/usr/bin/env python3
"""
D207-1-0: Docker Diagnostics Collector

Purpose: Collect Docker/DB state for evidence (monitoring blackbox)

Usage:
    python scripts/ops/collect_docker_diag.py --out logs/evidence/xxx --phase before
    python scripts/ops/collect_docker_diag.py --out logs/evidence/xxx --phase after
"""

import argparse
import subprocess
import sys
from pathlib import Path
from datetime import datetime


def run_command(cmd: list, output_file: Path):
    """Run command and save output"""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30
        )
        output_file.write_text(
            f"Command: {' '.join(cmd)}\n"
            f"Exit Code: {result.returncode}\n"
            f"Stdout:\n{result.stdout}\n"
            f"Stderr:\n{result.stderr}\n",
            encoding='utf-8'
        )
        return result.returncode == 0
    except Exception as e:
        output_file.write_text(f"ERROR: {e}\n", encoding='utf-8')
        return False


def main():
    parser = argparse.ArgumentParser(description="Collect Docker diagnostics")
    parser.add_argument("--out", required=True, help="Output directory")
    parser.add_argument("--phase", required=True, choices=["before", "after"])
    parser.add_argument("--compose", default="infra/docker-compose.yml")
    args = parser.parse_args()
    
    evidence_dir = Path(args.out)
    evidence_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    phase = args.phase
    
    # docker compose ps
    run_command(
        ["docker", "compose", "-f", args.compose, "ps"],
        evidence_dir / f"docker_ps_{phase}_{timestamp}.txt"
    )
    
    # docker compose logs (postgres tail)
    run_command(
        ["docker", "compose", "-f", args.compose, "logs", "--tail", "100", "postgres"],
        evidence_dir / f"docker_logs_postgres_{phase}_{timestamp}.txt"
    )
    
    # docker stats (single snapshot)
    run_command(
        ["docker", "stats", "--no-stream", "--format", "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}"],
        evidence_dir / f"docker_stats_{phase}_{timestamp}.txt"
    )
    
    print(f"[{phase.upper()}] Diagnostics collected: {evidence_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
