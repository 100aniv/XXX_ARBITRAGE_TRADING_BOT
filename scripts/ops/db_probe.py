#!/usr/bin/env python3
"""
D207-1-0: DB Connection Probe

Purpose: Verify DB connection and record current state

Usage:
    python scripts/ops/db_probe.py --out logs/evidence/xxx/probe.txt
    python scripts/ops/db_probe.py --dsn postgresql://user:pass@host:5432/db --out probe.txt
"""

import argparse
import os
import sys
from pathlib import Path
from datetime import datetime

try:
    import psycopg2
except ImportError:
    print("ERROR: psycopg2 not installed. Install with: pip install psycopg2-binary")
    sys.exit(1)


def probe_db(dsn: str, output_file: Path):
    """Probe DB connection and save result"""
    try:
        conn = psycopg2.connect(dsn)
        cur = conn.cursor()
        
        # Simple query
        cur.execute("SELECT 1 AS test, current_user, current_database(), now();")
        row = cur.fetchone()
        
        result = (
            f"[DB PROBE SUCCESS] {datetime.now().isoformat()}\n"
            f"DSN: {dsn}\n"
            f"Test: {row[0]}\n"
            f"Current User: {row[1]}\n"
            f"Current DB: {row[2]}\n"
            f"Server Time: {row[3]}\n"
        )
        
        cur.close()
        conn.close()
        
        output_file.write_text(result, encoding='utf-8')
        print(result)
        return 0
        
    except Exception as e:
        error_msg = (
            f"[DB PROBE FAIL] {datetime.now().isoformat()}\n"
            f"DSN: {dsn}\n"
            f"Error: {e}\n"
        )
        output_file.write_text(error_msg, encoding='utf-8')
        print(error_msg, file=sys.stderr)
        return 1


def main():
    parser = argparse.ArgumentParser(description="DB connection probe")
    parser.add_argument("--dsn", help="PostgreSQL DSN (optional, defaults to env POSTGRES_DSN)")
    parser.add_argument("--out", required=True, help="Output file")
    args = parser.parse_args()
    
    dsn = args.dsn or os.getenv(
        "POSTGRES_DSN",
        "postgresql://arbitrage:arbitrage@localhost:5432/arbitrage"
    )
    
    output_file = Path(args.out)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    return probe_db(dsn, output_file)


if __name__ == "__main__":
    sys.exit(main())
