#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
D90-3: Zone Profile Tuning v1 - Results Analysis

모든 실행 결과를 수집하고 분석하는 스크립트.
"""

import json
from pathlib import Path
from typing import Dict, List

# 실행 디렉터리 리스트
run_dirs = [
    "logs/d87-3/d90_3_advisory_z2_focus_advisory_run1",
    "logs/d87-3/d90_3_advisory_z2_focus_advisory_run2",
    "logs/d87-3/d90_3_advisory_z2_balanced_advisory_run1",
    "logs/d87-3/d90_3_advisory_z2_balanced_advisory_run2",
    "logs/d87-3/d90_3_advisory_z23_focus_advisory_run1",
    "logs/d87-3/d90_3_advisory_z23_focus_advisory_run2",
    "logs/d87-3/d90_3_advisory_z2_conservative_advisory_run1",
    "logs/d87-3/d90_3_advisory_z2_conservative_advisory_run2",
]

# Calibration 로드
calib_path = Path("logs/d86-1/calibration_20251207_123906.json")
with open(calib_path, 'r') as f:
    calib = json.load(f)

zones = [(z['entry_min'], z['entry_max']) for z in calib['zones']]

# 결과 수집
results = []

for run_dir in run_dirs:
    run_path = Path(run_dir)
    
    # KPI 파일 찾기
    kpi_files = list(run_path.glob("kpi_*.json"))
    if not kpi_files:
        print(f"[WARNING] No KPI file found in {run_dir}")
        continue
    
    kpi_path = kpi_files[0]
    
    # KPI 로드
    with open(kpi_path, 'r') as f:
        kpi = json.load(f)
    
    # Fill events 로드
    fill_events_path = Path(kpi['fill_events_path'])
    if not fill_events_path.exists():
        print(f"[WARNING] Fill events file not found: {fill_events_path}")
        continue
    
    events = []
    with open(fill_events_path, 'r') as f:
        for line in f:
            events.append(json.loads(line))
    
    # BUY 이벤트만 필터링
    buys = [e for e in events if e['side'].lower() == 'buy']
    
    # Zone별 카운트
    zone_counts = [0, 0, 0, 0]
    for e in buys:
        for i, (mn, mx) in enumerate(zones):
            if mn <= e['entry_bps'] < mx:
                zone_counts[i] += 1
                break
    
    total_buys = len(buys)
    zone_percentages = [c / total_buys * 100 if total_buys > 0 else 0 for c in zone_counts]
    
    # 프로파일 이름 추출
    profile_name = run_path.name.replace("d90_3_", "").replace("_advisory_run1", "").replace("_advisory_run2", "")
    run_idx = 1 if "run1" in run_path.name else 2
    
    results.append({
        'profile_name': profile_name,
        'run_idx': run_idx,
        'kpi': kpi,
        'zone_counts': zone_counts,
        'zone_percentages': zone_percentages,
        'total_buys': total_buys,
    })

# 프로파일별 집계
from collections import defaultdict
import statistics

by_profile = defaultdict(list)
for r in results:
    by_profile[r['profile_name']].append(r)

# 출력
print("=" * 80)
print("D90-3: Zone Profile Tuning v1 - Results Summary")
print("=" * 80)
print()

# 프로파일별 요약 테이블
print("## Profile Comparison")
print()
print("| Profile | Runs | PnL (mean ± std) | Z1% | Z2% | Z3% | Z4% |")
print("|---------|------|------------------|-----|-----|-----|-----|")

for profile_name in sorted(by_profile.keys()):
    runs = by_profile[profile_name]
    
    pnls = [r['kpi']['total_pnl_usd'] for r in runs]
    z1_pcts = [r['zone_percentages'][0] for r in runs]
    z2_pcts = [r['zone_percentages'][1] for r in runs]
    z3_pcts = [r['zone_percentages'][2] for r in runs]
    z4_pcts = [r['zone_percentages'][3] for r in runs]
    
    pnl_mean = statistics.mean(pnls)
    pnl_std = statistics.stdev(pnls) if len(pnls) > 1 else 0
    z1_mean = statistics.mean(z1_pcts)
    z2_mean = statistics.mean(z2_pcts)
    z3_mean = statistics.mean(z3_pcts)
    z4_mean = statistics.mean(z4_pcts)
    
    print(f"| {profile_name} | {len(runs)} | ${pnl_mean:.2f} ± ${pnl_std:.2f} | "
          f"{z1_mean:.1f}% | {z2_mean:.1f}% | {z3_mean:.1f}% | {z4_mean:.1f}% |")

print()
print("=" * 80)
print()

# 상세 결과
print("## Detailed Results")
print()

for profile_name in sorted(by_profile.keys()):
    runs = by_profile[profile_name]
    
    print(f"### {profile_name}")
    print()
    
    for r in runs:
        print(f"**Run {r['run_idx']}:**")
        print(f"- PnL: ${r['kpi']['total_pnl_usd']:.2f}")
        print(f"- Trades: {r['kpi']['entry_trades']}")
        print(f"- Duration: {r['kpi']['actual_duration_seconds']:.1f}s")
        print(f"- Zone Distribution: Z1={r['zone_percentages'][0]:.1f}%, Z2={r['zone_percentages'][1]:.1f}%, "
              f"Z3={r['zone_percentages'][2]:.1f}%, Z4={r['zone_percentages'][3]:.1f}%")
        print()
    
    print()

print("=" * 80)
print("Analysis complete!")
print("=" * 80)
