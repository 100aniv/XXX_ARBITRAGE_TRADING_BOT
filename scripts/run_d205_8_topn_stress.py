#!/usr/bin/env python3
import sys
from pathlib import Path

# Project root bootstrap
sys.path.insert(0, str(Path(__file__).parent.parent))

from arbitrage.v2.tools.topn_stress import cli_main


if __name__ == "__main__":
    sys.exit(cli_main())
