#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
D81-1: Advanced Fill Model & Partial Fill Validation Helper

12분 Real PAPER 결과에 대해
- D80-4 기준 (8개) 재사용
- D81-1 추가 기준 (Partial Fill ≥ 1)
를 검증하여 PASS/FAIL 판정하는 헬퍼 스크립트.

Usage:
    python scripts/validate_d81_1_kpi.py [--kpi-path KPI_JSON] [--trade-log-path TRADE_LOG_JSONL]
"""

import json
import sys
import argparse
from pathlib import Path
from typing import Dict, Any, List


def validate_d80_4_criteria(metrics: Dict[str, Any]) -> tuple:
    """
    D80-4 기준 검증 (재사용)
    
    Returns:
        (passed: bool, reasons: List[str])
    """
    reasons = []
    passed = True
    
    # 1. Duration
    duration = metrics.get("duration_minutes", 0)
    if duration >= 10.0:
        reasons.append(f"✅ Duration: {duration:.1f} min >= 10.0 min")
    else:
        reasons.append(f"❌ Duration: {duration:.1f} min < 10.0 min")
        passed = False
    
    # 2. Entry trades
    entry_trades = metrics.get("entry_trades", 0)
    if entry_trades >= 1:
        reasons.append(f"✅ Entry trades: {entry_trades} >= 1")
    else:
        reasons.append(f"❌ Entry trades: {entry_trades} < 1")
        passed = False
    
    # 3. Round trips
    round_trips = metrics.get("round_trips_completed", 0)
    if round_trips >= 1:
        reasons.append(f"✅ Round trips: {round_trips} >= 1")
    else:
        reasons.append(f"❌ Round trips: {round_trips} < 1")
        passed = False
    
    # 4. Buy slippage
    buy_slippage = metrics.get("avg_buy_slippage_bps", 0)
    if 0.1 <= buy_slippage <= 10.0:
        reasons.append(f"✅ Buy slippage: {buy_slippage:.2f} bps in [0.1, 10.0]")
    else:
        reasons.append(f"❌ Buy slippage: {buy_slippage:.2f} bps out of [0.1, 10.0]")
        passed = False
    
    # 5. Sell slippage
    sell_slippage = metrics.get("avg_sell_slippage_bps", 0)
    if 0.1 <= sell_slippage <= 10.0:
        reasons.append(f"✅ Sell slippage: {sell_slippage:.2f} bps in [0.1, 10.0]")
    else:
        reasons.append(f"❌ Sell slippage: {sell_slippage:.2f} bps out of [0.1, 10.0]")
        passed = False
    
    # 6. Loop latency avg
    loop_latency_avg = metrics.get("loop_latency_avg_ms", 0)
    if loop_latency_avg < 80.0:
        reasons.append(f"✅ Loop latency avg: {loop_latency_avg:.2f}ms < 80ms")
    else:
        reasons.append(f"❌ Loop latency avg: {loop_latency_avg:.2f}ms >= 80ms")
        passed = False
    
    # 7. Loop latency p99
    loop_latency_p99 = metrics.get("loop_latency_p99_ms", 0)
    if loop_latency_p99 < 500.0:
        reasons.append(f"✅ Loop latency p99: {loop_latency_p99:.2f}ms < 500ms")
    else:
        reasons.append(f"❌ Loop latency p99: {loop_latency_p99:.2f}ms >= 500ms")
        passed = False
    
    # 8. Guard triggers (informational)
    guard_triggers = metrics.get("guard_triggers", 0)
    reasons.append(f"ℹ️  Guard triggers: {guard_triggers}")
    
    # 9. Win rate (informational)
    win_rate = metrics.get("win_rate_pct", 0)
    reasons.append(f"ℹ️  Win rate: {win_rate:.1f}% (informational)")
    
    return passed, reasons


def validate_d81_1_partial_fill(trade_log_path: Path) -> tuple:
    """
    D81-1 추가 기준: Partial Fill ≥ 1
    
    Trade Log를 파싱하여 0 < fill_ratio < 1.0인 trade 카운트.
    
    Returns:
        (passed: bool, reasons: List[str], partial_fill_count: int)
    """
    reasons = []
    partial_fill_count = 0
    
    if not trade_log_path.exists():
        reasons.append(f"❌ Trade log not found: {trade_log_path}")
        return False, reasons, 0
    
    try:
        with open(trade_log_path, "r") as f:
            for line in f:
                if not line.strip():
                    continue
                
                trade = json.loads(line)
                buy_fill_ratio = trade.get("buy_fill_ratio", 1.0)
                sell_fill_ratio = trade.get("sell_fill_ratio", 1.0)
                
                # Partial fill: 0 < fill_ratio < 1.0
                if (0 < buy_fill_ratio < 1.0) or (0 < sell_fill_ratio < 1.0):
                    partial_fill_count += 1
    except Exception as e:
        reasons.append(f"❌ Failed to parse trade log: {e}")
        return False, reasons, 0
    
    # 최소 1건 이상
    if partial_fill_count >= 1:
        reasons.append(f"✅ Partial fill: {partial_fill_count} >= 1")
        passed = True
    else:
        reasons.append(f"❌ Partial fill: {partial_fill_count} < 1 (NO PARTIAL FILL DETECTED)")
        passed = False
    
    return passed, reasons, partial_fill_count


def main():
    """Main validation"""
    parser = argparse.ArgumentParser(description="D81-1: Advanced Fill Model Validation")
    parser.add_argument(
        "--kpi-path",
        type=str,
        default="logs/d81-1/kpi_advanced_fill.json",
        help="Path to KPI JSON file",
    )
    parser.add_argument(
        "--trade-log-path",
        type=str,
        default=None,
        help="Path to Trade Log JSONL file (optional, auto-detected if not provided)",
    )
    
    args = parser.parse_args()
    
    kpi_path = Path(args.kpi_path)
    
    if not kpi_path.exists():
        print(f"❌ KPI file not found: {kpi_path}")
        return 1
    
    # Load KPI
    with open(kpi_path) as f:
        metrics = json.load(f)
    
    # Auto-detect trade log path if not provided
    if args.trade_log_path is None:
        # Try to find trade log in logs/d81-1/trades/<run_id>/top20_trade_log.jsonl
        trade_log_dir = Path("logs/d81-1/trades")
        if trade_log_dir.exists():
            run_dirs = sorted([d for d in trade_log_dir.iterdir() if d.is_dir()], key=lambda x: x.stat().st_mtime, reverse=True)
            if run_dirs:
                trade_log_path = run_dirs[0] / "top20_trade_log.jsonl"
            else:
                print(f"❌ No run directories found in {trade_log_dir}")
                return 1
        else:
            print(f"❌ Trade log directory not found: {trade_log_dir}")
            return 1
    else:
        trade_log_path = Path(args.trade_log_path)
    
    print("=" * 80)
    print("[D81-1] Advanced Fill Model & Partial Fill Validation")
    print("=" * 80)
    print(f"KPI File: {kpi_path}")
    print(f"Trade Log: {trade_log_path}")
    print(f"Profile: fill_model + partial_fill")
    print("=" * 80)
    
    # D80-4 기준 검증
    d80_4_passed, d80_4_reasons = validate_d80_4_criteria(metrics)
    
    for reason in d80_4_reasons:
        print(reason)
    
    # D81-1 추가 기준 검증
    d81_1_passed, d81_1_reasons, partial_fill_count = validate_d81_1_partial_fill(trade_log_path)
    
    for reason in d81_1_reasons:
        print(reason)
    
    # 전체 결과
    print("=" * 80)
    
    if d80_4_passed and d81_1_passed:
        print("✅ [RESULT] ALL ACCEPTANCE CRITERIA PASSED")
        print(f"   - D80-4 기준: PASS")
        print(f"   - D81-1 Partial Fill: {partial_fill_count} detected")
        return 0
    else:
        print("❌ [RESULT] SOME ACCEPTANCE CRITERIA FAILED")
        if not d80_4_passed:
            print(f"   - D80-4 기준: FAIL")
        if not d81_1_passed:
            print(f"   - D81-1 Partial Fill: {partial_fill_count} detected (required ≥1)")
        return 1


if __name__ == "__main__":
    sys.exit(main())
