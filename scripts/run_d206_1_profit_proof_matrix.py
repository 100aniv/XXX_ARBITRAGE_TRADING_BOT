#!/usr/bin/env python3
"""Thin wrapper for D206-1 profitability proof tool."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from arbitrage.v2.tools.profit_proof_matrix import main


if __name__ == "__main__":
    raise SystemExit(main())
