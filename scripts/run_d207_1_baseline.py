#!/usr/bin/env python3
"""
D207-1 REAL 20m Baseline Runner (Direct Execution)
"""

import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from arbitrage.v2.harness.paper_runner import main

if __name__ == "__main__":
    sys.argv = [
        "run_d207_1_baseline.py",
        "--phase", "baseline",
        "--duration", "20",
        "--output-dir", "logs/evidence/d207_1_baseline_20m_20260119_recovery",
        "--use-real-data",
        "--disable-early-stop",
    ]
    exit_code = main()
    sys.exit(exit_code)
