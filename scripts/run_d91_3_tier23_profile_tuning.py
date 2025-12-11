#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
D91-3: Tier2/3 Zone Profile Tuning (XRP/SOL/DOGE)

심볼별 프로파일 후보군을 20분 SHORT PAPER로 실행하여 Zone 분포 및 PnL 비교.

목표:
- XRP, SOL (Tier2), DOGE (Tier3) 각 심볼별 프로파일 튜닝
- strict/advisory 모드별 2~3개 후보 프로파일 비교
- Zone 분포 + PnL 기준으로 Best Profile 선정

Usage:
    # 전체 심볼 자동 실행 (기본)
    python scripts/run_d91_3_tier23_profile_tuning.py
    
    # 특정 심볼만
    python scripts/run_d91_3_tier23_profile_tuning.py --symbols XRP,SOL
    
    # dry-run (실행 계획만 출력)
    python scripts/run_d91_3_tier23_profile_tuning.py --dry-run
    
    # 짧은 duration (smoke test)
    python scripts/run_d91_3_tier23_profile_tuning.py --duration-minutes 5 --symbols XRP

Author: arbitrage-lite project
Date: 2025-12-11 (D91-3)
"""

import argparse
import json
import logging
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

# 프로젝트 루트 추가
sys.path.insert(0, str(Path(__file__).parent.parent))

from arbitrage.config.zone_profiles_loader_v2 import (
    load_zone_profiles_v2_with_fallback,
    select_profile_for_symbol,
    get_zone_boundaries_for_symbol,
)

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)


# ===== 심볼별 프로파일 후보군 정의 =====
SYMBOL_PROFILE_CANDIDATES = {
    "XRP": {
        "strict": ["strict_uniform_light"],  # D91-2 검증 완료, 재확인
        "advisory": ["advisory_z2_focus", "advisory_z3_focus"],  # Z2 vs Z3 집중 비교
    },
    "SOL": {
        "strict": ["strict_uniform_light"],
        "advisory": ["advisory_z2_focus", "advisory_z3_focus"],  # XRP와 동일 후보군
    },
    "DOGE": {
        "strict": ["strict_uniform_light"],
        "advisory": ["advisory_z2_conservative", "advisory_z2_balanced"],  # 보수적 후보군
    },
}

# 기본 설정
DEFAULT_DURATION_MINUTES = 20
DEFAULT_CALIBRATION_PATH = "logs/d86-1/calibration_20251207_123906.json"
DEFAULT_MARKET = "upbit"
DEFAULT_SEED = 93  # D91-3 고유 seed


def parse_zone_distribution(fill_events_path: Path, calibration_path: Path) -> Dict[str, Any]:
    """
    Fill events와 Calibration을 기반으로 Zone 분포 계산.
    
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
    if fill_events_path.exists():
        with open(fill_events_path, 'r') as f:
            for line in f:
                events.append(json.loads(line))
    else:
        logger.warning(f"Fill events file not found: {fill_events_path}")
        return {'total_buys': 0, 'zone_counts': [0, 0, 0, 0], 'zone_percentages': [0, 0, 0, 0]}
    
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


def run_single_profile_paper(
    symbol: str,
    market: str,
    mode: str,
    profile_name: str,
    duration_minutes: int,
    calibration_path: str,
    seed: int,
    output_base_dir: Path
) -> Tuple[bool, Dict[str, Any]]:
    """
    단일 심볼/모드/프로파일 조합에 대해 20m PAPER 실행.
    
    Args:
        symbol: 심볼 이름
        market: 마켓 이름
        mode: "strict" or "advisory"
        profile_name: Zone Profile 이름
        duration_minutes: 실행 시간 (분)
        calibration_path: Calibration JSON 경로
        seed: Entry BPS seed
        output_base_dir: 로그 출력 기본 디렉터리
    
    Returns:
        (success, result_dict)
    """
    # 세션 태그 생성: d91_3_{symbol}_{profile}_{mode}_{duration}m
    session_tag = f"d91_3_{symbol.lower()}_{profile_name}_{mode}_{duration_minutes}m"
    
    # 출력 디렉터리
    output_dir = output_base_dir / session_tag
    output_dir.mkdir(parents=True, exist_ok=True)
    
    logger.info("=" * 80)
    logger.info(f"[D91-3] Running: {symbol} ({mode}, {duration_minutes}분)")
    logger.info(f"Profile: {profile_name}")
    logger.info(f"Output: {output_dir}")
    logger.info("=" * 80)
    
    # D84-2 Runner 호출
    duration_seconds = duration_minutes * 60
    cmd = [
        sys.executable,
        "scripts/run_d84_2_calibrated_fill_paper.py",
        "--duration-seconds", str(duration_seconds),
        "--l2-source", market,
        "--fillmodel-mode", mode,
        "--calibration-path", calibration_path,
        "--entry-bps-mode", "zone_random",
        "--entry-bps-zone-profile", profile_name,
        "--entry-bps-seed", str(seed),
        "--session-tag", session_tag,
    ]
    
    logger.info(f"Command: {' '.join(cmd)}")
    
    try:
        start_time = time.time()
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        elapsed = time.time() - start_time
        
        logger.info(f"[D91-3] Completed in {elapsed:.1f}s")
        
        # Zone 분포 계산
        fill_events_path = list(output_dir.glob("fill_events_*.jsonl"))
        if not fill_events_path:
            logger.error(f"No fill_events file found in {output_dir}")
            return False, {}
        
        zone_stats = parse_zone_distribution(fill_events_path[0], Path(calibration_path))
        
        # zone_stats.json 저장
        zone_stats_path = output_dir / "zone_stats.json"
        with open(zone_stats_path, 'w') as f:
            json.dump(zone_stats, f, indent=2)
        
        logger.info(f"[D91-3] Zone stats saved: {zone_stats_path}")
        
        # KPI 로드 (있으면)
        kpi_files = list(output_dir.glob("kpi_*.json"))
        kpi_data = {}
        if kpi_files:
            with open(kpi_files[0], 'r') as f:
                kpi_data = json.load(f)
        
        # 결과 요약
        result_summary = {
            'symbol': symbol,
            'market': market,
            'mode': mode,
            'profile': profile_name,
            'duration_minutes': duration_minutes,
            'success': True,
            'zone_stats': zone_stats,
            'kpi': kpi_data,
            'output_dir': str(output_dir),
        }
        
        # 로그 출력
        logger.info(f"[D91-3] Zone distribution:")
        for i, (count, pct) in enumerate(zip(zone_stats['zone_counts'], zone_stats['zone_percentages'])):
            logger.info(f"  Z{i+1}:   {count:3d} ({pct:5.1f}%)")
        
        return True, result_summary
        
    except subprocess.CalledProcessError as e:
        logger.error(f"[D91-3] FAILED: {e}")
        logger.error(f"STDERR: {e.stderr}")
        return False, {
            'symbol': symbol,
            'mode': mode,
            'profile': profile_name,
            'success': False,
            'error': str(e),
        }


def generate_execution_plan(
    symbols: List[str],
    mode: str,
    duration_minutes: int
) -> List[Dict[str, Any]]:
    """
    실행 계획 생성 (심볼×모드×프로파일 조합).
    
    Args:
        symbols: 심볼 리스트
        mode: "strict", "advisory", or "both"
        duration_minutes: 실행 시간 (분)
    
    Returns:
        실행 계획 리스트 [{symbol, mode, profile_name}, ...]
    """
    plan = []
    
    for symbol in symbols:
        if symbol not in SYMBOL_PROFILE_CANDIDATES:
            logger.warning(f"Symbol '{symbol}' not in SYMBOL_PROFILE_CANDIDATES, skipping")
            continue
        
        candidates = SYMBOL_PROFILE_CANDIDATES[symbol]
        
        # strict 모드
        if mode in ["strict", "both"]:
            for profile in candidates.get("strict", []):
                plan.append({
                    'symbol': symbol,
                    'mode': 'strict',
                    'profile_name': profile,
                    'duration_minutes': duration_minutes,
                })
        
        # advisory 모드
        if mode in ["advisory", "both"]:
            for profile in candidates.get("advisory", []):
                plan.append({
                    'symbol': symbol,
                    'mode': 'advisory',
                    'profile_name': profile,
                    'duration_minutes': duration_minutes,
                })
    
    return plan


def save_summary(results: List[Dict[str, Any]], output_path: Path):
    """
    전체 결과 요약을 JSON으로 저장.
    
    Args:
        results: 실행 결과 리스트
        output_path: 출력 파일 경로
    """
    summary = {}
    
    for result in results:
        symbol = result['symbol']
        mode = result['mode']
        profile = result['profile']
        
        if symbol not in summary:
            summary[symbol] = {}
        
        if mode not in summary[symbol]:
            summary[symbol][mode] = {}
        
        summary[symbol][mode][profile] = {
            'success': result.get('success', False),
            'zone_stats': result.get('zone_stats', {}),
            'kpi': result.get('kpi', {}),
            'output_dir': result.get('output_dir', ''),
        }
    
    with open(output_path, 'w') as f:
        json.dump(summary, f, indent=2)
    
    logger.info(f"[D91-3] Summary saved: {output_path}")


def main():
    parser = argparse.ArgumentParser(description="D91-3: Tier2/3 Zone Profile Tuning")
    parser.add_argument(
        "--symbols",
        type=str,
        default="XRP,SOL,DOGE",
        help="쉼표로 구분된 심볼 리스트 (예: XRP,SOL,DOGE)"
    )
    parser.add_argument(
        "--duration-minutes",
        type=int,
        default=DEFAULT_DURATION_MINUTES,
        help=f"실행 시간 (분, 기본값: {DEFAULT_DURATION_MINUTES})"
    )
    parser.add_argument(
        "--mode",
        type=str,
        choices=["strict", "advisory", "both"],
        default="both",
        help="실행 모드 (strict, advisory, or both)"
    )
    parser.add_argument(
        "--calibration-path",
        type=str,
        default=DEFAULT_CALIBRATION_PATH,
        help=f"Calibration JSON 경로 (기본값: {DEFAULT_CALIBRATION_PATH})"
    )
    parser.add_argument(
        "--market",
        type=str,
        default=DEFAULT_MARKET,
        help=f"마켓 (기본값: {DEFAULT_MARKET})"
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=DEFAULT_SEED,
        help=f"Entry BPS seed (기본값: {DEFAULT_SEED})"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="실행 계획만 출력 (실제 실행 안 함)"
    )
    
    args = parser.parse_args()
    
    # 심볼 리스트 파싱
    symbols = [s.strip().upper() for s in args.symbols.split(",")]
    
    # 실행 계획 생성
    plan = generate_execution_plan(symbols, args.mode, args.duration_minutes)
    
    logger.info("=" * 80)
    logger.info("[D91-3] Tier2/3 Profile Tuning - Execution Plan")
    logger.info("=" * 80)
    logger.info(f"Symbols: {symbols}")
    logger.info(f"Mode: {args.mode}")
    logger.info(f"Duration: {args.duration_minutes} minutes")
    logger.info(f"Total combinations: {len(plan)}")
    logger.info("")
    
    for i, item in enumerate(plan, 1):
        logger.info(f"  {i}. {item['symbol']:4s} | {item['mode']:8s} | {item['profile_name']}")
    
    if args.dry_run:
        logger.info("")
        logger.info("[D91-3] Dry-run mode: execution plan generated, exiting.")
        return 0
    
    # 실제 실행
    logger.info("")
    logger.info("=" * 80)
    logger.info("[D91-3] Starting execution...")
    logger.info("=" * 80)
    
    output_base_dir = Path("logs/d91-3")
    output_base_dir.mkdir(parents=True, exist_ok=True)
    
    results = []
    failed_count = 0
    
    for i, item in enumerate(plan, 1):
        logger.info(f"\n[D91-3] Progress: {i}/{len(plan)}")
        
        success, result = run_single_profile_paper(
            symbol=item['symbol'],
            market=args.market,
            mode=item['mode'],
            profile_name=item['profile_name'],
            duration_minutes=item['duration_minutes'],
            calibration_path=args.calibration_path,
            seed=args.seed,
            output_base_dir=output_base_dir
        )
        
        results.append(result)
        
        if not success:
            failed_count += 1
            logger.error(f"[D91-3] ❌ FAILED: {item['symbol']} {item['mode']} {item['profile_name']}")
        else:
            logger.info(f"[D91-3] ✅ SUCCESS: {item['symbol']} {item['mode']} {item['profile_name']}")
    
    # 요약 저장
    summary_path = output_base_dir / "d91_3_summary.json"
    save_summary(results, summary_path)
    
    # 최종 결과
    logger.info("")
    logger.info("=" * 80)
    logger.info("[D91-3] FINAL SUMMARY")
    logger.info("=" * 80)
    logger.info(f"Total combinations: {len(plan)}")
    logger.info(f"Success: {len(plan) - failed_count}")
    logger.info(f"Failed: {failed_count}")
    logger.info(f"Summary: {summary_path}")
    logger.info("=" * 80)
    
    # Return code: 모든 성공 0, 일부 실패 1
    if failed_count > 0:
        # 각 심볼별로 최소 1개 이상 성공했는지 확인
        symbol_success = {}
        for result in results:
            if result.get('success'):
                symbol_success[result['symbol']] = True
        
        if len(symbol_success) >= len(symbols):
            logger.info("[D91-3] At least one profile per symbol succeeded: PASS")
            return 0
        else:
            logger.error("[D91-3] Some symbols have no successful profiles: FAIL")
            return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
