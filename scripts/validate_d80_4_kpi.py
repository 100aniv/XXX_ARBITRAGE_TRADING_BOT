#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
D80-4: FINAL Acceptance Validation Helper

12분 Real PAPER 결과(kpi_d80_4_validation.json)에 대해
evaluate_validation(metrics, ValidationProfile.FILL_MODEL)을 실행하여
PASS/FAIL 판정을 확인하는 헬퍼 스크립트.
"""

import json
import sys
from pathlib import Path
from enum import Enum
from dataclasses import dataclass
from typing import Dict, Any, List


# ValidationProfile 복사 (run_d77_0_topn_arbitrage_paper.py와 동일)
class ValidationProfile(str, Enum):
    NONE = "none"
    FILL_MODEL = "fill_model"
    TOPN_RESEARCH = "topn_research"


@dataclass
class ValidationResult:
    profile: ValidationProfile
    passed: bool
    reasons: List[str]


def evaluate_validation(
    metrics: Dict[str, Any], profile: ValidationProfile
) -> ValidationResult:
    """Validation logic (copied from runner)"""
    if profile == ValidationProfile.NONE:
        return ValidationResult(
            profile=profile, passed=True, reasons=["No validation requested"]
        )
    
    reasons = []
    passed = True
    
    if profile == ValidationProfile.FILL_MODEL:
        # D80-4 Acceptance Criteria
        duration = metrics.get("duration_minutes", 0)
        if duration >= 10.0:
            reasons.append(f"✅ Duration: {duration:.1f} min >= 10.0 min")
        else:
            reasons.append(f"❌ Duration: {duration:.1f} min < 10.0 min")
            passed = False
        
        entry_trades = metrics.get("entry_trades", 0)
        if entry_trades >= 1:
            reasons.append(f"✅ Entry trades: {entry_trades} >= 1")
        else:
            reasons.append(f"❌ Entry trades: {entry_trades} < 1")
            passed = False
        
        round_trips = metrics.get("round_trips_completed", 0)
        if round_trips >= 1:
            reasons.append(f"✅ Round trips: {round_trips} >= 1")
        else:
            reasons.append(f"❌ Round trips: {round_trips} < 1")
            passed = False
        
        buy_slippage = metrics.get("avg_buy_slippage_bps", 0)
        if 0.1 <= buy_slippage <= 5.0:
            reasons.append(f"✅ Buy slippage: {buy_slippage:.2f} bps in [0.1, 5.0]")
        else:
            reasons.append(f"❌ Buy slippage: {buy_slippage:.2f} bps out of [0.1, 5.0]")
            passed = False
        
        sell_slippage = metrics.get("avg_sell_slippage_bps", 0)
        if 0.1 <= sell_slippage <= 5.0:
            reasons.append(f"✅ Sell slippage: {sell_slippage:.2f} bps in [0.1, 5.0]")
        else:
            reasons.append(f"❌ Sell slippage: {sell_slippage:.2f} bps out of [0.1, 5.0]")
            passed = False
        
        partial_fills = metrics.get("partial_fills_count", 0)
        if partial_fills > 0:
            reasons.append(f"ℹ️  Partial fills: {partial_fills} (scenario tested)")
        else:
            reasons.append(f"ℹ️  Partial fills: 0 (not tested, OK for D80-4)")
        
        loop_latency_avg = metrics.get("loop_latency_avg_ms", 0)
        if loop_latency_avg < 80.0:
            reasons.append(f"✅ Loop latency avg: {loop_latency_avg:.2f}ms < 80ms")
        else:
            reasons.append(f"❌ Loop latency avg: {loop_latency_avg:.2f}ms >= 80ms")
            passed = False
        
        loop_latency_p99 = metrics.get("loop_latency_p99_ms", 0)
        if loop_latency_p99 < 500.0:
            reasons.append(f"✅ Loop latency p99: {loop_latency_p99:.2f}ms < 500ms")
        else:
            reasons.append(f"❌ Loop latency p99: {loop_latency_p99:.2f}ms >= 500ms")
            passed = False
        
        guard_triggers = metrics.get("guard_triggers", 0)
        reasons.append(f"ℹ️  Guard triggers: {guard_triggers}")
        
        win_rate = metrics.get("win_rate_pct", 0)
        reasons.append(f"ℹ️  Win rate: {win_rate:.1f}% (informational, not criteria)")
    
    return ValidationResult(profile=profile, passed=passed, reasons=reasons)


def main():
    """Main validation"""
    kpi_path = Path("logs/d80-4/real_paper_validation/kpi_d80_4_validation.json")
    
    if not kpi_path.exists():
        print(f"❌ KPI file not found: {kpi_path}")
        sys.exit(1)
    
    with open(kpi_path) as f:
        metrics = json.load(f)
    
    print("=" * 80)
    print("[D80-4] FINAL Acceptance Validation")
    print("=" * 80)
    print(f"KPI File: {kpi_path}")
    print(f"Profile: fill_model")
    print("=" * 80)
    
    result = evaluate_validation(metrics, ValidationProfile.FILL_MODEL)
    
    for reason in result.reasons:
        print(reason)
    
    print("=" * 80)
    
    if result.passed:
        print("✅ [RESULT] ALL ACCEPTANCE CRITERIA PASSED")
        return 0
    else:
        print("❌ [RESULT] SOME ACCEPTANCE CRITERIA FAILED")
        return 1


if __name__ == "__main__":
    sys.exit(main())
