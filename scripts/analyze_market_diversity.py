#!/usr/bin/env python3
"""
D205-14-3: Market Data Diversity Analyzer

market.ndjson 파일의 품질을 분석:
- ticks_count
- unique_lines_count / unique_ratio
- spread 분포 (min/median/p90/max)
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, Any, List
import statistics

sys.path.insert(0, str(Path(__file__).parent.parent))


def analyze_market_file(market_path: Path) -> Dict[str, Any]:
    """
    market.ndjson 파일 분석
    
    Args:
        market_path: market.ndjson 경로
        
    Returns:
        분석 결과 딕셔너리
    """
    if not market_path.exists():
        return {
            "status": "FAIL",
            "reason": f"File not found: {market_path}",
        }
    
    lines = []
    unique_lines = set()
    spreads_bps = []
    
    try:
        with open(market_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                
                lines.append(line)
                unique_lines.add(line)
                
                try:
                    data = json.loads(line)
                    upbit_bid = data.get("upbit_bid", 0)
                    upbit_ask = data.get("upbit_ask", 0)
                    
                    if upbit_bid > 0 and upbit_ask > 0:
                        spread_bps = ((upbit_ask - upbit_bid) / upbit_bid) * 10000
                        spreads_bps.append(spread_bps)
                
                except json.JSONDecodeError:
                    continue
    
    except Exception as e:
        return {
            "status": "FAIL",
            "reason": f"Read error: {e}",
        }
    
    ticks_count = len(lines)
    unique_count = len(unique_lines)
    unique_ratio = unique_count / ticks_count if ticks_count > 0 else 0.0
    
    spread_stats = {}
    if spreads_bps:
        spread_stats = {
            "min": round(min(spreads_bps), 2),
            "median": round(statistics.median(spreads_bps), 2),
            "p90": round(statistics.quantiles(spreads_bps, n=10)[8], 2) if len(spreads_bps) >= 10 else None,
            "max": round(max(spreads_bps), 2),
            "mean": round(statistics.mean(spreads_bps), 2),
        }
    
    result = {
        "status": "PASS",
        "ticks_count": ticks_count,
        "unique_lines_count": unique_count,
        "unique_ratio": round(unique_ratio, 3),
        "spread_bps_stats": spread_stats,
    }
    
    return result


def main(argv=None):
    """Main entry point"""
    parser = argparse.ArgumentParser(description="D205-14-3: Market Data Diversity Analyzer")
    parser.add_argument(
        "--market-file",
        type=Path,
        required=True,
        help="Path to market.ndjson file",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output JSON file path (default: same dir as market file, market_stats.json)",
    )
    
    args = parser.parse_args(argv)
    
    result = analyze_market_file(args.market_file)
    
    print(json.dumps(result, indent=2, ensure_ascii=False))
    
    if args.output:
        output_path = args.output
    else:
        output_path = args.market_file.parent / "market_stats.json"
    
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    
    print(f"\n[STATS] Saved to: {output_path}")
    
    if result["status"] == "FAIL":
        sys.exit(1)
    
    if result["ticks_count"] < 1000:
        print(f"\n[WARNING] ticks_count ({result['ticks_count']}) < 1000")
    
    if result["unique_ratio"] < 0.50:
        print(f"\n[WARNING] unique_ratio ({result['unique_ratio']}) < 0.50")


if __name__ == "__main__":
    main()
