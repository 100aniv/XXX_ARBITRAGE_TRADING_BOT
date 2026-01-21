#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
D90-3: Zone Profile Tuning v1 - Sweep Harness

Zone Profile 후보들을 일괄 실행하고 결과를 비교 분석하는 스크립트.

Usage:
    python scripts/run_d90_3_zone_profile_sweep.py \\
        --profiles advisory_z2_focus,advisory_z2_balanced,advisory_z23_focus \\
        --duration 1200 \\
        --mode advisory \\
        --repeat 2

Author: arbitrage-lite project
Date: 2025-12-10
"""

import argparse
import json
import logging
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)


def parse_zone_distribution(fill_events_path: Path, calibration_path: Path) -> Dict[str, Any]:
    """
    Fill events와 Calibration을 기반으로 Zone 분포를 계산.
    
    Args:
        fill_events_path: Fill events JSONL 파일 경로
        calibration_path: Calibration JSON 파일 경로
    
    Returns:
        Zone 분포 딕셔너리
    """
    # Calibration 로드
    with open(calibration_path, 'r') as f:
        calib = json.load(f)
    
    zones = [(z['entry_min'], z['entry_max']) for z in calib['zones']]
    
    # Fill events 로드
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
    
    total = len(buys)
    
    return {
        'total_buys': total,
        'zone_counts': zone_counts,
        'zone_percentages': [c / total * 100 if total > 0 else 0 for c in zone_counts],
    }


def run_single_profile(
    profile_name: str,
    mode: str,
    duration: int,
    run_idx: int,
    calibration_path: Path,
) -> Dict[str, Any]:
    """
    단일 Zone Profile을 실행하고 결과를 반환.
    
    Args:
        profile_name: Zone Profile 이름
        mode: FillModel 모드 (strict/advisory)
        duration: 실행 시간 (초)
        run_idx: 실행 인덱스 (seed/time offset용)
        calibration_path: Calibration JSON 파일 경로
    
    Returns:
        실행 결과 딕셔너리 (KPI + Zone 분포)
    """
    session_tag = f"d90_3_{profile_name}_{mode}_run{run_idx}"
    seed = 90 + run_idx  # seed offset
    
    cmd = [
        sys.executable,
        "scripts/run_d84_2_calibrated_fill_paper.py",
        "--duration-seconds", str(duration),
        "--l2-source", "real",
        "--fillmodel-mode", mode,
        "--calibration-path", str(calibration_path),
        "--entry-bps-mode", "zone_random",
        "--entry-bps-zone-profile", profile_name,
        "--entry-bps-min", "5.0",
        "--entry-bps-max", "25.0",
        "--entry-bps-seed", str(seed),
        "--session-tag", session_tag,
    ]
    
    logger.info("=" * 80)
    logger.info(f"[D90-3] Running: {profile_name} ({mode}, run {run_idx})")
    logger.info(f"Command: {' '.join(cmd)}")
    logger.info("=" * 80)
    
    start_time = time.time()
    
    try:
        result = subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            text=True,
        )
        
        elapsed = time.time() - start_time
        logger.info(f"[D90-3] Completed in {elapsed:.1f}s")
        
        # KPI 파일 경로 추출
        kpi_path = None
        for line in result.stdout.split('\n'):
            if 'kpi_' in line and '.json' in line:
                # 경로 추출 (다양한 포맷 대응)
                if 'KPI 저장 완료:' in line:
                    kpi_path = Path(line.split('KPI 저장 완료:')[-1].strip())
                    break
        
        if not kpi_path:
            # 기본 경로 추정
            kpi_path = Path(f"logs/d87-3/{session_tag}") / f"kpi_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json"
        
        # KPI 로드
        if kpi_path.exists():
            with open(kpi_path, 'r') as f:
                kpi = json.load(f)
        else:
            logger.warning(f"[D90-3] KPI file not found: {kpi_path}")
            kpi = {}
        
        # Fill events 경로
        fill_events_path = kpi.get('fill_events_path')
        if fill_events_path:
            fill_events_path = Path(fill_events_path)
        else:
            # 기본 경로 추정
            fill_events_path = kpi_path.parent / f"fill_events_{kpi.get('session_id', 'unknown')}.jsonl"
        
        # Zone 분포 계산
        if fill_events_path.exists():
            zone_dist = parse_zone_distribution(fill_events_path, calibration_path)
        else:
            logger.warning(f"[D90-3] Fill events file not found: {fill_events_path}")
            zone_dist = {}
        
        return {
            'profile_name': profile_name,
            'mode': mode,
            'run_idx': run_idx,
            'session_tag': session_tag,
            'seed': seed,
            'kpi': kpi,
            'zone_distribution': zone_dist,
            'elapsed_seconds': elapsed,
            'success': True,
        }
        
    except subprocess.CalledProcessError as e:
        logger.error(f"[D90-3] Failed: {e}")
        logger.error(f"STDOUT: {e.stdout}")
        logger.error(f"STDERR: {e.stderr}")
        
        return {
            'profile_name': profile_name,
            'mode': mode,
            'run_idx': run_idx,
            'session_tag': session_tag,
            'seed': seed,
            'success': False,
            'error': str(e),
        }


def aggregate_results(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    여러 실행 결과를 프로파일별로 집계.
    
    Args:
        results: 실행 결과 리스트
    
    Returns:
        프로파일별 집계 딕셔너리
    """
    from collections import defaultdict
    import statistics
    
    # 프로파일별 그룹화
    by_profile = defaultdict(list)
    for r in results:
        if r['success']:
            key = f"{r['profile_name']}_{r['mode']}"
            by_profile[key].append(r)
    
    # 집계
    aggregated = {}
    for key, runs in by_profile.items():
        profile_name = runs[0]['profile_name']
        mode = runs[0]['mode']
        
        # KPI 집계
        pnls = [r['kpi'].get('total_pnl_usd', 0) for r in runs if 'kpi' in r]
        trades = [r['kpi'].get('entry_trades', 0) for r in runs if 'kpi' in r]
        durations = [r['kpi'].get('actual_duration_seconds', 0) for r in runs if 'kpi' in r]
        
        # Zone 분포 집계
        z1_pcts = [r['zone_distribution']['zone_percentages'][0] for r in runs if 'zone_distribution' in r and r['zone_distribution']]
        z2_pcts = [r['zone_distribution']['zone_percentages'][1] for r in runs if 'zone_distribution' in r and r['zone_distribution']]
        z3_pcts = [r['zone_distribution']['zone_percentages'][2] for r in runs if 'zone_distribution' in r and r['zone_distribution']]
        z4_pcts = [r['zone_distribution']['zone_percentages'][3] for r in runs if 'zone_distribution' in r and r['zone_distribution']]
        
        aggregated[key] = {
            'profile_name': profile_name,
            'mode': mode,
            'run_count': len(runs),
            'pnl': {
                'mean': statistics.mean(pnls) if pnls else 0,
                'stdev': statistics.stdev(pnls) if len(pnls) > 1 else 0,
                'values': pnls,
            },
            'trades': {
                'mean': statistics.mean(trades) if trades else 0,
                'values': trades,
            },
            'duration': {
                'mean': statistics.mean(durations) if durations else 0,
                'values': durations,
            },
            'zone_percentages': {
                'z1': {'mean': statistics.mean(z1_pcts) if z1_pcts else 0, 'values': z1_pcts},
                'z2': {'mean': statistics.mean(z2_pcts) if z2_pcts else 0, 'values': z2_pcts},
                'z3': {'mean': statistics.mean(z3_pcts) if z3_pcts else 0, 'values': z3_pcts},
                'z4': {'mean': statistics.mean(z4_pcts) if z4_pcts else 0, 'values': z4_pcts},
            },
        }
    
    return aggregated


def generate_summary_markdown(aggregated: Dict[str, Any], output_path: Path):
    """
    집계 결과를 Markdown 요약 파일로 생성.
    
    Args:
        aggregated: 프로파일별 집계 딕셔너리
        output_path: 출력 파일 경로
    """
    lines = []
    lines.append("# D90-3: Zone Profile Tuning v1 - Sweep Summary")
    lines.append("")
    lines.append(f"**Generated:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## Profile Comparison")
    lines.append("")
    lines.append("| Profile | Mode | Runs | PnL (mean ± std) | Z1% | Z2% | Z3% | Z4% | ΔP(Z2) |")
    lines.append("|---------|------|------|------------------|-----|-----|-----|-----|--------|")
    
    # Strict 기준선 찾기
    strict_z2 = None
    for key, data in aggregated.items():
        if data['mode'] == 'strict':
            strict_z2 = data['zone_percentages']['z2']['mean']
            break
    
    for key, data in sorted(aggregated.items()):
        profile = data['profile_name']
        mode = data['mode']
        runs = data['run_count']
        pnl_mean = data['pnl']['mean']
        pnl_std = data['pnl']['stdev']
        z1 = data['zone_percentages']['z1']['mean']
        z2 = data['zone_percentages']['z2']['mean']
        z3 = data['zone_percentages']['z3']['mean']
        z4 = data['zone_percentages']['z4']['mean']
        
        delta_z2 = z2 - strict_z2 if strict_z2 else 0
        
        lines.append(
            f"| {profile} | {mode} | {runs} | "
            f"${pnl_mean:.2f} ± ${pnl_std:.2f} | "
            f"{z1:.1f}% | {z2:.1f}% | {z3:.1f}% | {z4:.1f}% | "
            f"{delta_z2:+.1f}%p |"
        )
    
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## Detailed Results")
    lines.append("")
    
    for key, data in sorted(aggregated.items()):
        lines.append(f"### {data['profile_name']} ({data['mode']})")
        lines.append("")
        lines.append(f"- **Runs:** {data['run_count']}")
        lines.append(f"- **PnL:** ${data['pnl']['mean']:.2f} ± ${data['pnl']['stdev']:.2f}")
        lines.append(f"  - Values: {[f'${v:.2f}' for v in data['pnl']['values']]}")
        lines.append(f"- **Trades:** {data['trades']['mean']:.0f}")
        lines.append(f"- **Duration:** {data['duration']['mean']:.1f}s")
        lines.append(f"- **Zone Distribution:**")
        lines.append(f"  - Z1: {data['zone_percentages']['z1']['mean']:.1f}%")
        lines.append(f"  - Z2: {data['zone_percentages']['z2']['mean']:.1f}%")
        lines.append(f"  - Z3: {data['zone_percentages']['z3']['mean']:.1f}%")
        lines.append(f"  - Z4: {data['zone_percentages']['z4']['mean']:.1f}%")
        lines.append("")
    
    # 파일 저장
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    
    logger.info(f"[D90-3] Summary saved: {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description="D90-3: Zone Profile Tuning v1 - Sweep Harness"
    )
    parser.add_argument(
        "--profiles",
        type=str,
        required=True,
        help="Comma-separated list of Zone Profile names (e.g., advisory_z2_focus,advisory_z2_balanced)"
    )
    parser.add_argument(
        "--duration",
        type=int,
        default=1200,
        help="Duration in seconds for each run (default: 1200 = 20m)"
    )
    parser.add_argument(
        "--mode",
        type=str,
        choices=["strict", "advisory", "both"],
        default="advisory",
        help="FillModel mode (strict/advisory/both, default: advisory)"
    )
    parser.add_argument(
        "--repeat",
        type=int,
        default=2,
        help="Number of runs per profile (default: 2)"
    )
    parser.add_argument(
        "--calibration-path",
        type=str,
        default="logs/d86-1/calibration_20251207_123906.json",
        help="Calibration JSON file path"
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="logs/d87-3/d90_3_profile_sweep",
        help="Output directory for summary files"
    )
    
    args = parser.parse_args()
    
    # 프로파일 리스트 파싱
    profiles = [p.strip() for p in args.profiles.split(',')]
    
    # 모드 리스트
    if args.mode == "both":
        modes = ["strict", "advisory"]
    else:
        modes = [args.mode]
    
    calibration_path = Path(args.calibration_path)
    if not calibration_path.exists():
        logger.error(f"[D90-3] Calibration file not found: {calibration_path}")
        sys.exit(1)
    
    # 출력 디렉터리 생성
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    logger.info("=" * 80)
    logger.info("[D90-3] Zone Profile Tuning v1 - Sweep Harness")
    logger.info("=" * 80)
    logger.info(f"Profiles: {profiles}")
    logger.info(f"Modes: {modes}")
    logger.info(f"Duration: {args.duration}s ({args.duration/60:.1f}m)")
    logger.info(f"Repeat: {args.repeat}")
    logger.info(f"Calibration: {calibration_path}")
    logger.info(f"Output: {output_dir}")
    logger.info("=" * 80)
    logger.info("")
    
    # 실행
    results = []
    total_runs = len(profiles) * len(modes) * args.repeat
    current_run = 0
    
    for profile in profiles:
        for mode in modes:
            for run_idx in range(1, args.repeat + 1):
                current_run += 1
                logger.info(f"[D90-3] Progress: {current_run}/{total_runs}")
                
                result = run_single_profile(
                    profile_name=profile,
                    mode=mode,
                    duration=args.duration,
                    run_idx=run_idx,
                    calibration_path=calibration_path,
                )
                results.append(result)
                
                # 다음 실행 전 대기 (Redis/시스템 안정화)
                if current_run < total_runs:
                    logger.info("[D90-3] Waiting 10s before next run...")
                    time.sleep(10)
    
    # 집계
    logger.info("")
    logger.info("=" * 80)
    logger.info("[D90-3] Aggregating results...")
    logger.info("=" * 80)
    
    aggregated = aggregate_results(results)
    
    # JSON 저장
    summary_json_path = output_dir / "summary.json"
    with open(summary_json_path, 'w', encoding='utf-8') as f:
        json.dump({
            'results': results,
            'aggregated': aggregated,
        }, f, indent=2)
    logger.info(f"[D90-3] Summary JSON saved: {summary_json_path}")
    
    # Markdown 저장
    summary_md_path = output_dir / "summary.md"
    generate_summary_markdown(aggregated, summary_md_path)
    
    logger.info("")
    logger.info("=" * 80)
    logger.info("[D90-3] Sweep completed!")
    logger.info("=" * 80)
    logger.info(f"Total runs: {total_runs}")
    logger.info(f"Success: {sum(1 for r in results if r['success'])}")
    logger.info(f"Failed: {sum(1 for r in results if not r['success'])}")
    logger.info(f"Summary: {summary_md_path}")
    logger.info("=" * 80)


if __name__ == "__main__":
    main()
