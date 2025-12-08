#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
D88-0: Zone Distribution Analyzer

Fill Events 파일에서 Zone 분포를 분석한다.
"""

import json
import sys
from pathlib import Path
from collections import Counter

def analyze_zone_distribution(fill_events_path: Path):
    """
    Fill Events 파일에서 Zone 분포를 분석
    
    Args:
        fill_events_path: Fill Events JSONL 파일 경로
    
    Returns:
        분석 결과 dict
    """
    # Zone 정의 (D86 Calibration 기준)
    zones = {
        "Z1": (5.0, 7.0),
        "Z2": (7.0, 12.0),
        "Z3": (12.0, 20.0),
        "Z4": (20.0, 30.0),
    }
    
    # Fill Events 로드
    events = []
    with open(fill_events_path, "r") as f:
        for line in f:
            event = json.loads(line.strip())
            events.append(event)
    
    # Entry BPS별 Zone 분류
    entry_trades = [e for e in events if e["side"] == "buy"]
    zone_counts = Counter()
    
    for event in entry_trades:
        entry_bps = event.get("entry_bps", 0.0)
        
        # Zone 매칭
        matched_zone = None
        for zone_id, (zmin, zmax) in zones.items():
            if zmin <= entry_bps < zmax:
                matched_zone = zone_id
                break
        
        if matched_zone:
            zone_counts[matched_zone] += 1
        else:
            zone_counts["UNMATCHED"] += 1
    
    # 결과 출력
    total_trades = sum(zone_counts.values())
    print("=" * 80)
    print("D88-0: Zone Distribution Analysis")
    print("=" * 80)
    print(f"Fill Events File: {fill_events_path}")
    print(f"Total Entry Trades: {total_trades}")
    print(f"Total Fill Events: {len(events)} (BUY + SELL)")
    print("")
    print("Zone Distribution:")
    print("-" * 80)
    
    for zone_id in ["Z1", "Z2", "Z3", "Z4", "UNMATCHED"]:
        count = zone_counts.get(zone_id, 0)
        percentage = (count / total_trades * 100) if total_trades > 0 else 0.0
        print(f"  {zone_id}: {count:3d} trades ({percentage:5.1f}%)")
    
    print("=" * 80)
    
    # Acceptance Criteria 검증
    z1_count = zone_counts.get("Z1", 0)
    z2_count = zone_counts.get("Z2", 0)
    z3_count = zone_counts.get("Z3", 0)
    z4_count = zone_counts.get("Z4", 0)
    unmatched_count = zone_counts.get("UNMATCHED", 0)
    
    print("\nAcceptance Criteria:")
    print("-" * 80)
    
    # C1: 모든 Zone에 최소 1개 이상의 트레이드
    c1_pass = z1_count > 0 and z2_count > 0 and z3_count > 0 and z4_count > 0
    print(f"  C1 (All Zones Covered): {'✅ PASS' if c1_pass else '❌ FAIL'}")
    print(f"     Z1={z1_count}, Z2={z2_count}, Z3={z3_count}, Z4={z4_count}")
    
    # C2: Z2만 100% 아님 (다양성 확보)
    z2_percentage = (z2_count / total_trades * 100) if total_trades > 0 else 0.0
    c2_pass = z2_percentage < 90.0  # Z2가 90% 미만이면 PASS
    print(f"  C2 (No Z2 Dominance): {'✅ PASS' if c2_pass else '❌ FAIL'}")
    print(f"     Z2={z2_percentage:.1f}% (목표: < 90%)")
    
    # C3: Unmatched 비율 < 5%
    unmatched_percentage = (unmatched_count / total_trades * 100) if total_trades > 0 else 0.0
    c3_pass = unmatched_percentage < 5.0
    print(f"  C3 (Low Unmatched Rate): {'✅ PASS' if c3_pass else '❌ FAIL'}")
    print(f"     Unmatched={unmatched_percentage:.1f}% (목표: < 5%)")
    
    print("=" * 80)
    
    # 최종 판정
    all_pass = c1_pass and c2_pass and c3_pass
    print(f"\n최종 판정: {'✅ PASS' if all_pass else '❌ FAIL'}")
    print("=" * 80)
    
    return {
        "total_trades": total_trades,
        "total_events": len(events),
        "zone_counts": dict(zone_counts),
        "acceptance_criteria": {
            "C1_all_zones_covered": c1_pass,
            "C2_no_z2_dominance": c2_pass,
            "C3_low_unmatched_rate": c3_pass,
            "overall": all_pass,
        }
    }

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/d88_0_analyze_zone_distribution.py <fill_events.jsonl>")
        sys.exit(1)
    
    fill_events_path = Path(sys.argv[1])
    if not fill_events_path.exists():
        print(f"Error: File not found: {fill_events_path}")
        sys.exit(1)
    
    result = analyze_zone_distribution(fill_events_path)
    
    # 결과를 JSON으로 저장
    output_path = fill_events_path.parent / "zone_distribution_analysis.json"
    with open(output_path, "w") as f:
        json.dump(result, f, indent=2)
    
    print(f"\nAnalysis result saved to: {output_path}")
    
    # Exit code: 0 (PASS) or 1 (FAIL)
    sys.exit(0 if result["acceptance_criteria"]["overall"] else 1)
