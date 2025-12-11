#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
D91-2: Multi-Symbol Zone Distribution Validation

BTC/ETH/XRP (Upbit) 심볼별 Zone Profile v2 검증을 위한 20분 SHORT PAPER Runner.

목표:
- YAML v2.0.0 + symbol_mappings를 사용하여 심볼별 Zone Profile 선택
- BTC/ETH (Tier1), XRP (Tier2) 각각 20분 PAPER 실행
- Zone 분포가 설계 의도와 일치하는지 검증

Usage:
    # BTC strict 20분
    python scripts/run_d91_2_multi_symbol_zone_validation.py --symbol BTC --mode strict --duration-minutes 20
    
    # ETH strict 20분
    python scripts/run_d91_2_multi_symbol_zone_validation.py --symbol ETH --mode strict --duration-minutes 20
    
    # XRP strict 20분 (Tier2 프로파일)
    python scripts/run_d91_2_multi_symbol_zone_validation.py --symbol XRP --mode strict --duration-minutes 20
    
    # XRP advisory 20분 (experimental advisory_z3_focus)
    python scripts/run_d91_2_multi_symbol_zone_validation.py --symbol XRP --mode advisory --duration-minutes 20

Author: arbitrage-lite project
Date: 2025-12-11 (D91-2)
"""

import argparse
import json
import logging
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

# 프로젝트 루트 추가
sys.path.insert(0, str(Path(__file__).parent.parent))

# v2 로더 임포트
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


def run_symbol_validation(
    symbol: str,
    mode: str,
    duration_minutes: int,
    calibration_path: Path,
    market: str = "upbit",
) -> Dict[str, Any]:
    """
    단일 심볼에 대해 Zone Profile v2 기반 20분 PAPER 실행.
    
    Args:
        symbol: 심볼 이름 (BTC, ETH, XRP)
        mode: FillModel 모드 (strict, advisory)
        duration_minutes: 실행 시간 (분)
        calibration_path: Calibration JSON 파일 경로
        market: 마켓 이름 (기본값 upbit)
    
    Returns:
        실행 결과 딕셔너리
    """
    # v2 YAML 로드
    logger.info("=" * 80)
    logger.info(f"[D91-2] Loading Zone Profiles v2 YAML...")
    v2_data = load_zone_profiles_v2_with_fallback()
    
    profiles = v2_data["profiles"]
    symbol_mappings = v2_data["symbol_mappings"]
    source = v2_data["source"]
    
    logger.info(f"[D91-2] Zone Profiles loaded from: {source}")
    logger.info(f"[D91-2] Available profiles: {list(profiles.keys())}")
    logger.info(f"[D91-2] Symbol mappings: {list(symbol_mappings.keys())}")
    
    # 심볼별 Zone Profile 선택
    profile = select_profile_for_symbol(
        symbol=symbol,
        market=market,
        mode=mode,
        profiles=profiles,
        symbol_mappings=symbol_mappings
    )
    
    logger.info(f"[D91-2] Selected profile for {symbol} ({market}, {mode}): {profile.name}")
    logger.info(f"[D91-2] Zone weights: {profile.zone_weights}")
    
    # 심볼별 Zone Boundaries 가져오기
    zone_boundaries = get_zone_boundaries_for_symbol(
        symbol=symbol,
        market=market,
        symbol_mappings=symbol_mappings
    )
    
    logger.info(f"[D91-2] Zone boundaries: {zone_boundaries}")
    
    # Session tag 생성
    session_tag = f"d91_2_{symbol.lower()}_{mode}_20m"
    session_id = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    
    # 로그 디렉터리 설정
    output_dir = Path(__file__).parent.parent / "logs" / "d91-2" / session_tag
    output_dir.mkdir(parents=True, exist_ok=True)
    
    logger.info(f"[D91-2] Output directory: {output_dir}")
    logger.info("=" * 80)
    
    # D84-2 Runner 호출 (subprocess)
    duration_seconds = duration_minutes * 60
    seed = 91  # D91-2 고유 seed
    
    # 심볼에 따라 L2 source 결정 (현재는 모두 upbit, 향후 확장 가능)
    l2_source = "upbit"
    
    cmd = [
        sys.executable,
        "scripts/run_d84_2_calibrated_fill_paper.py",
        "--duration-seconds", str(duration_seconds),
        "--l2-source", l2_source,
        "--fillmodel-mode", mode,
        "--calibration-path", str(calibration_path),
        "--entry-bps-mode", "zone_random",
        "--entry-bps-zone-profile", profile.name,  # v2에서 선택한 프로파일
        "--entry-bps-seed", str(seed),
        "--session-tag", session_tag,
    ]
    
    # Zone boundaries도 전달 (필요 시 - 현재 D84-2 Runner가 calibration에서 가져옴)
    # 향후 확장: --entry-bps-zone-boundaries 옵션 추가
    
    logger.info(f"[D91-2] Running: {symbol} ({mode}, {duration_minutes}분)")
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
        logger.info(f"[D91-2] Completed in {elapsed:.1f}s")
        
        # KPI 파일 경로 추정
        kpi_path = output_dir / f"kpi_{session_id}.json"
        
        # KPI 로드 (여러 위치 시도)
        kpi = {}
        for possible_kpi_path in [
            kpi_path,
            output_dir / f"kpi_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json",
        ]:
            if possible_kpi_path.exists():
                with open(possible_kpi_path, 'r') as f:
                    kpi = json.load(f)
                kpi_path = possible_kpi_path
                break
        
        # kpi.json 파일들 찾기 (최신 파일 사용)
        if not kpi:
            kpi_files = list(output_dir.glob("kpi_*.json"))
            if kpi_files:
                kpi_path = max(kpi_files, key=lambda p: p.stat().st_mtime)
                with open(kpi_path, 'r') as f:
                    kpi = json.load(f)
        
        # Fill events 경로
        fill_events_path = kpi.get('fill_events_path')
        if fill_events_path:
            fill_events_path = Path(fill_events_path)
        else:
            # 최신 fill_events.jsonl 찾기
            fill_events_files = list(output_dir.glob("fill_events_*.jsonl"))
            if fill_events_files:
                fill_events_path = max(fill_events_files, key=lambda p: p.stat().st_mtime)
        
        # Zone 분포 계산
        zone_dist = {}
        if fill_events_path and fill_events_path.exists():
            zone_dist = parse_zone_distribution(fill_events_path, calibration_path)
            logger.info(f"[D91-2] Zone distribution calculated: {zone_dist}")
            
            # Zone 분포 JSON 저장
            zone_stats_path = output_dir / "zone_stats.json"
            with open(zone_stats_path, 'w') as f:
                json.dump(zone_dist, f, indent=2)
            logger.info(f"[D91-2] Zone stats saved: {zone_stats_path}")
        else:
            logger.warning(f"[D91-2] Fill events file not found: {fill_events_path}")
        
        return {
            'symbol': symbol,
            'market': market,
            'mode': mode,
            'profile_name': profile.name,
            'profile_weights': profile.zone_weights,
            'zone_boundaries': zone_boundaries,
            'session_tag': session_tag,
            'output_dir': str(output_dir),
            'kpi': kpi,
            'zone_distribution': zone_dist,
            'elapsed_seconds': elapsed,
            'success': True,
        }
        
    except subprocess.CalledProcessError as e:
        logger.error(f"[D91-2] Failed: {e}")
        logger.error(f"STDOUT: {e.stdout}")
        logger.error(f"STDERR: {e.stderr}")
        
        return {
            'symbol': symbol,
            'market': market,
            'mode': mode,
            'session_tag': session_tag,
            'success': False,
            'error': str(e),
        }


def main():
    """메인 함수."""
    parser = argparse.ArgumentParser(
        description="D91-2: Multi-Symbol Zone Distribution Validation"
    )
    
    parser.add_argument(
        "--symbol",
        type=str,
        required=True,
        choices=["BTC", "ETH", "XRP"],
        help="심볼 이름 (BTC, ETH, XRP)"
    )
    
    parser.add_argument(
        "--mode",
        type=str,
        required=True,
        choices=["strict", "advisory"],
        help="FillModel 모드 (strict, advisory)"
    )
    
    parser.add_argument(
        "--duration-minutes",
        type=int,
        default=20,
        help="실행 시간 (분, 기본값 20)"
    )
    
    parser.add_argument(
        "--calibration-path",
        type=str,
        default="logs/d86-1/calibration_20251207_123906.json",
        help="Calibration JSON 파일 경로"
    )
    
    parser.add_argument(
        "--market",
        type=str,
        default="upbit",
        help="마켓 이름 (기본값 upbit)"
    )
    
    args = parser.parse_args()
    
    # Calibration 경로 검증
    calibration_path = Path(args.calibration_path)
    if not calibration_path.exists():
        logger.error(f"Calibration file not found: {calibration_path}")
        sys.exit(1)
    
    # 실행
    result = run_symbol_validation(
        symbol=args.symbol,
        mode=args.mode,
        duration_minutes=args.duration_minutes,
        calibration_path=calibration_path,
        market=args.market,
    )
    
    # 요약 출력
    logger.info("")
    logger.info("=" * 80)
    logger.info("[D91-2] VALIDATION SUMMARY")
    logger.info("=" * 80)
    logger.info(f"Symbol: {result['symbol']}")
    logger.info(f"Market: {result['market']}")
    logger.info(f"Mode: {result['mode']}")
    logger.info(f"Profile: {result.get('profile_name', 'N/A')}")
    logger.info(f"Success: {result['success']}")
    
    if result['success']:
        zone_dist = result.get('zone_distribution', {})
        if zone_dist:
            logger.info(f"Total BUY trades: {zone_dist['total_buys']}")
            logger.info(f"Zone distribution:")
            for i, (count, pct) in enumerate(zip(zone_dist['zone_counts'], zone_dist['zone_percentages'])):
                logger.info(f"  Z{i+1}: {count:4d} ({pct:5.1f}%)")
        
        logger.info(f"Output directory: {result['output_dir']}")
    else:
        logger.error(f"Error: {result.get('error', 'Unknown')}")
    
    logger.info("=" * 80)
    
    # 종료 코드
    sys.exit(0 if result['success'] else 1)


if __name__ == "__main__":
    main()
