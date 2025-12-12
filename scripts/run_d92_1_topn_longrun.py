#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
D92-1: TopN Multi-Symbol 1h LONGRUN (Top10)

Zone Profile 시스템의 실전 멀티 심볼 1h 검증.

목표:
- Zone Profile v2 (D91-0~3)를 TopN 멀티 심볼 PAPER 1h 실행에 적용
- BTC/ETH (Tier1), XRP/SOL (Tier2), DOGE (Tier3) Best Profile 검증
- 1시간 PAPER 실행으로 Zone 분포, PnL, Trade 수 종합 검증

Usage:
    # 기본 실행 (Top10, 1h, advisory)
    python scripts/run_d92_1_topn_longrun.py
    
    # Custom 설정
    python scripts/run_d92_1_topn_longrun.py --top-n 20 --duration-minutes 120 --mode advisory
    
    # Dry-run (구조 확인용)
    python scripts/run_d92_1_topn_longrun.py --dry-run

Author: arbitrage-lite project
Date: 2025-12-12 (D92-1)
"""

import argparse
import asyncio
import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

# 프로젝트 루트 추가
sys.path.insert(0, str(Path(__file__).parent.parent))

from arbitrage.config.zone_profiles_loader_v2 import (
    load_zone_profiles_v2_with_fallback,
    select_profile_for_symbol,
    get_zone_boundaries_for_symbol,
)
from arbitrage.core.zone_profile_applier import ZoneProfileApplier
from arbitrage.domain.topn_provider import TopNMode

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)


# ===== D91-3 Best Profile 정의 =====
BEST_PROFILES = {
    "BTC": {"mode": "advisory", "profile": "advisory_z2_focus"},  # Tier1
    "ETH": {"mode": "advisory", "profile": "advisory_z2_focus"},  # Tier1
    "XRP": {"mode": "advisory", "profile": "advisory_z2_focus"},  # Tier2 (D91-3 Best)
    "SOL": {"mode": "advisory", "profile": "advisory_z3_focus"},  # Tier2 (D91-3 Best)
    "DOGE": {"mode": "advisory", "profile": "advisory_z2_balanced"},  # Tier3 (D91-3 Best)
}

# 기본 설정
DEFAULT_TOP_N = 10
DEFAULT_DURATION_MINUTES = 60
DEFAULT_CALIBRATION_PATH = "logs/d86-1/calibration_20251207_123906.json"
DEFAULT_MARKET = "upbit"


def get_topn_symbols_mock(top_n: int = 10) -> List[str]:
    """
    TopN 심볼 조회 (Mock).
    
    실제 환경에서는 Universe Provider 또는 TopN Provider를 사용.
    D92-1에서는 핵심 5개 심볼 + 추가 심볼로 구성.
    
    Args:
        top_n: 상위 N개
    
    Returns:
        심볼 리스트
    """
    # D92-1 핵심 검증 대상 (5개)
    core_symbols = ["BTC", "ETH", "XRP", "SOL", "DOGE"]
    
    # 추가 심볼 (Upbit Top 기준)
    additional_symbols = [
        "ADA", "AVAX", "DOT", "MATIC", "LINK",
        "ATOM", "UNI", "ALGO", "XLM", "ETC",
        "BCH", "LTC", "TRX", "XTZ", "EOS"
    ]
    
    all_symbols = core_symbols + additional_symbols
    
    return all_symbols[:top_n]


def parse_zone_distribution(fill_events_path: Path, calibration_path: Path) -> Dict[str, Any]:
    """
    Fill events와 Calibration을 기반으로 Zone 분포 계산.
    
    Args:
        fill_events_path: Fill events JSONL 파일 경로
        calibration_path: Calibration JSON 파일 경로
    
    Returns:
        Zone 분포 딕셔너리
    """
    if not fill_events_path.exists():
        logger.warning(f"Fill events file not found: {fill_events_path}")
        return {
            'total_buys': 0,
            'zone_counts': [0, 0, 0, 0],
            'zone_percentages': [0.0, 0.0, 0.0, 0.0],
        }
    
    if not calibration_path.exists():
        logger.warning(f"Calibration file not found: {calibration_path}")
        return {
            'total_buys': 0,
            'zone_counts': [0, 0, 0, 0],
            'zone_percentages': [0.0, 0.0, 0.0, 0.0],
        }
    
    # Calibration 로드
    with open(calibration_path, 'r') as f:
        calib = json.load(f)
    
    zones = [(z['entry_min'], z['entry_max']) for z in calib['zones']]
    
    # Fill events 로드
    events = []
    with open(fill_events_path, 'r') as f:
        for line in f:
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    
    # BUY 이벤트만 필터링
    buys = [e for e in events if e.get('side', '').lower() == 'buy']
    
    # Zone별 카운트
    zone_counts = [0, 0, 0, 0]
    for e in buys:
        entry_bps = e.get('entry_bps', 0)
        for i, (mn, mx) in enumerate(zones):
            if mn <= entry_bps < mx:
                zone_counts[i] += 1
                break
    
    total = len(buys)
    
    return {
        'total_buys': total,
        'zone_counts': zone_counts,
        'zone_percentages': [c / total * 100 if total > 0 else 0 for c in zone_counts],
    }


def run_topn_longrun(
    top_n: int,
    duration_minutes: int,
    mode: str,
    calibration_path: Path,
    market: str = "upbit",
    dry_run: bool = False,
) -> Dict[str, Any]:
    """
    TopN 멀티 심볼 1h LONGRUN 실행.
    
    Args:
        top_n: Top N 심볼 수
        duration_minutes: 실행 시간 (분)
        mode: FillModel 모드 (advisory, strict)
        calibration_path: Calibration JSON 파일 경로
        market: 마켓 이름 (기본값 upbit)
        dry_run: True이면 실제 실행 없이 구조만 확인
    
    Returns:
        실행 결과 딕셔너리
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_id = f"d92_1_top{top_n}_{mode}_{duration_minutes}m_{timestamp}"
    log_dir = Path(f"logs/d92-1/{run_id}")
    log_dir.mkdir(parents=True, exist_ok=True)
    
    logger.info("=" * 80)
    logger.info(f"[D92-1] TopN Multi-Symbol {duration_minutes}m LONGRUN")
    logger.info("=" * 80)
    logger.info(f"Run ID: {run_id}")
    logger.info(f"Top N: {top_n}")
    logger.info(f"Duration: {duration_minutes} minutes")
    logger.info(f"Mode: {mode}")
    logger.info(f"Market: {market}")
    logger.info(f"Log Dir: {log_dir}")
    logger.info(f"Dry Run: {dry_run}")
    
    # v2 YAML 로드
    logger.info("=" * 80)
    logger.info(f"[D92-1] Loading Zone Profiles v2 YAML...")
    v2_data = load_zone_profiles_v2_with_fallback()
    
    profiles = v2_data["profiles"]
    symbol_mappings = v2_data["symbol_mappings"]
    source = v2_data["source"]
    
    logger.info(f"[D92-1] Zone Profiles loaded from: {source}")
    logger.info(f"[D92-1] Available profiles: {list(profiles.keys())}")
    logger.info(f"[D92-1] Symbol mappings: {list(symbol_mappings.keys())}")
    
    # TopN 심볼 선정
    logger.info("=" * 80)
    logger.info(f"[D92-1] Fetching Top{top_n} symbols...")
    symbols = get_topn_symbols_mock(top_n)
    logger.info(f"[D92-1] Selected {len(symbols)} symbols: {symbols}")
    
    # 심볼별 Zone Profile 매핑
    logger.info("=" * 80)
    logger.info(f"[D92-1] Mapping Zone Profiles to symbols...")
    
    symbol_profile_map = {}
    for symbol in symbols:
        # D91-3 Best Profile이 있으면 사용, 없으면 v2 YAML 기본값
        if symbol in BEST_PROFILES:
            best = BEST_PROFILES[symbol]
            profile_mode = best["mode"]
            expected_profile = best["profile"]
            logger.info(f"  {symbol}: Using D91-3 Best Profile ({profile_mode}/{expected_profile})")
        else:
            profile_mode = mode
            expected_profile = None
            logger.info(f"  {symbol}: Using v2 YAML default ({profile_mode})")
        
        # v2 로더로 프로파일 선택
        profile = select_profile_for_symbol(
            symbol=symbol,
            market=market,
            mode=profile_mode,
            profiles=profiles,
            symbol_mappings=symbol_mappings
        )
        
        zone_boundaries = get_zone_boundaries_for_symbol(
            symbol=symbol,
            market=market,
            symbol_mappings=symbol_mappings
        )
        
        # D92-4: threshold_bps 추출
        threshold_bps = None
        if symbol in symbol_mappings:
            mapping = symbol_mappings[symbol]
            if market == mapping.get("market"):
                threshold_bps = mapping.get("threshold_bps", None)
        
        symbol_profile_map[symbol] = {
            "profile_name": profile.name,
            "profile_weights": profile.zone_weights,
            "zone_boundaries": zone_boundaries,
            "mode": profile_mode,
        }
        
        # D92-4: threshold_bps가 있으면 추가
        if threshold_bps is not None:
            symbol_profile_map[symbol]["threshold_bps"] = threshold_bps
        
        logger.info(f"    → Profile: {profile.name}, Weights: {profile.zone_weights}")
    
    # 실행 설정 저장
    run_config = {
        "run_id": run_id,
        "timestamp": timestamp,
        "top_n": top_n,
        "duration_minutes": duration_minutes,
        "mode": mode,
        "market": market,
        "symbols": symbols,
        "symbol_profile_map": symbol_profile_map,
        "calibration_path": str(calibration_path),
        "v2_yaml_source": source,
    }
    
    config_path = log_dir / "run_config.json"
    with open(config_path, 'w') as f:
        json.dump(run_config, f, indent=2)
    logger.info(f"[D92-1] Run config saved: {config_path}")
    
    # D92-1-FIX: Zone Profile 매핑을 별도 JSON 파일로 저장 (run_d77_0로 전달)
    zone_profile_json_path = log_dir / "symbol_profiles.json"
    with open(zone_profile_json_path, 'w') as f:
        json.dump(symbol_profile_map, f, indent=2)
    logger.info(f"[D92-1-FIX] Zone Profiles saved: {zone_profile_json_path}")
    
    if dry_run:
        logger.info("=" * 80)
        logger.info("[D92-1] DRY-RUN mode - skipping actual execution")
        logger.info("=" * 80)
        return {
            "status": "dry_run",
            "run_id": run_id,
            "log_dir": str(log_dir),
            "symbols": symbols,
            "symbol_profile_map": symbol_profile_map,
        }
    
    # D92-1-FIX: 직접 함수 호출 (subprocess 제거)
    logger.info("=" * 80)
    logger.info(f"[D92-1-FIX] Starting PAPER execution (direct function call)...")
    logger.info("=" * 80)
    
    # ZoneProfileApplier 초기화
    zone_profile_applier = ZoneProfileApplier(symbol_profile_map)
    logger.info(f"[D92-1-FIX] ZoneProfileApplier initialized for {len(symbol_profile_map)} symbols")
    
    # TopN mode 매핑
    topn_mode_map = {
        5: TopNMode.TOP_10,  # TOP_5 없음, TOP_10 사용
        10: TopNMode.TOP_10,
        20: TopNMode.TOP_20,
        50: TopNMode.TOP_50,
        100: TopNMode.TOP_100,
    }
    
    if top_n not in topn_mode_map:
        logger.error(f"[D92-1-FIX] Invalid top_n: {top_n}")
        return {
            "status": "error",
            "error": f"Invalid top_n: {top_n}",
            "run_id": run_id,
        }
    
    universe_mode = topn_mode_map[top_n]
    
    # run_d77_0 임포트 및 실행
    from scripts.run_d77_0_topn_arbitrage_paper import D77PAPERRunner
    
    start_time = time.time()
    
    try:
        # D77PAPERRunner 초기화
        runner = D77PAPERRunner(
            universe_mode=universe_mode,
            data_source="real",
            duration_minutes=duration_minutes,
            config_path="configs/paper/topn_arb_baseline.yaml",
            monitoring_enabled=True,
            monitoring_port=9100,
            kpi_output_path=None,
            zone_profile_applier=zone_profile_applier,  # D92-1-FIX
        )
        
        logger.info(f"[D92-1-FIX] D77PAPERRunner initialized with Zone Profiles")
        logger.info(f"[D92-1-FIX] Starting {duration_minutes}-minute execution...")
        
        # 비동기 실행
        logger.info("[D92-1-FIX] Runner.run() starting...")
        metrics = asyncio.run(runner.run())
        logger.info(f"[D92-1-FIX] Runner.run() completed. Metrics: {metrics}")
        
        elapsed_time = time.time() - start_time
        returncode = 0
        elapsed_min = elapsed_time / 60
        
        if returncode == 0:
            logger.info("=" * 80)
            logger.info(f"[D92-1] PAPER execution completed successfully")
            logger.info(f"[D92-1] Elapsed time: {elapsed_min:.1f} minutes")
            logger.info("=" * 80)
            
            # Zone 분포 분석
            logger.info("[D92-1] Analyzing Zone distribution...")
            
            summary_results = {}
            for symbol in symbols:
                # D77-0 실행 결과에서 fill_events와 zone_stats 찾기
                # 실제 경로는 run_d77_0의 로그 구조에 따라 다를 수 있음
                # 여기서는 예시로 구조 정의
                symbol_log_dir = Path(f"logs/d82-0/trades")  # D82-0 TradeLogger 경로
                
                # Zone 분포 계산 (fill_events 기반)
                # 실제로는 D77-0 출력 구조에 맞춰 조정 필요
                zone_dist = {
                    'total_buys': 0,
                    'zone_counts': [0, 0, 0, 0],
                    'zone_percentages': [0.0, 0.0, 0.0, 0.0],
                }
                
                summary_results[symbol] = {
                    "profile": symbol_profile_map[symbol]["profile_name"],
                    "zone_distribution": zone_dist,
                }
                
                logger.info(f"  {symbol}: {zone_dist['total_buys']} trades")
            
            # Summary JSON 저장
            summary_path = log_dir / "d92_1_summary.json"
            summary_data = {
                "run_id": run_id,
                "status": "success",
                "elapsed_minutes": elapsed_min,
                "symbols": symbols,
                "results": summary_results,
                "run_config": run_config,
            }
            
            with open(summary_path, 'w') as f:
                json.dump(summary_data, f, indent=2)
            logger.info(f"[D92-1] Summary saved: {summary_path}")
            
            return summary_data
            
        else:
            logger.error("=" * 80)
            logger.error(f"[D92-1] PAPER execution failed with code {returncode}")
            logger.error(f"[D92-1] Check logs: {log_file}")
            logger.error("=" * 80)
            
            return {
                "status": "failed",
                "returncode": returncode,
                "run_id": run_id,
                "log_dir": str(log_dir),
                "elapsed_minutes": elapsed_min,
            }
    
    except Exception as e:
        logger.error(f"[D92-1] Exception during execution: {e}", exc_info=True)
        return {
            "status": "error",
            "error": str(e),
            "run_id": run_id,
        }


def main():
    """CLI 메인"""
    parser = argparse.ArgumentParser(description="D92-1: TopN Multi-Symbol 1h LONGRUN")
    parser.add_argument(
        "--top-n",
        type=int,
        default=DEFAULT_TOP_N,
        help=f"Top N 심볼 수 (default: {DEFAULT_TOP_N})",
    )
    parser.add_argument(
        "--duration-minutes",
        type=int,
        default=DEFAULT_DURATION_MINUTES,
        help=f"실행 시간 (분, default: {DEFAULT_DURATION_MINUTES})",
    )
    parser.add_argument(
        "--mode",
        type=str,
        choices=["advisory", "strict"],
        default="advisory",
        help="FillModel 모드 (default: advisory)",
    )
    parser.add_argument(
        "--calibration-path",
        type=str,
        default=DEFAULT_CALIBRATION_PATH,
        help=f"Calibration JSON 경로 (default: {DEFAULT_CALIBRATION_PATH})",
    )
    parser.add_argument(
        "--market",
        type=str,
        default=DEFAULT_MARKET,
        help=f"마켓 이름 (default: {DEFAULT_MARKET})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="실행 계획만 출력 (실제 실행 없음)",
    )
    
    args = parser.parse_args()
    
    calibration_path = Path(args.calibration_path)
    
    result = run_topn_longrun(
        top_n=args.top_n,
        duration_minutes=args.duration_minutes,
        mode=args.mode,
        calibration_path=calibration_path,
        market=args.market,
        dry_run=args.dry_run,
    )
    
    logger.info("=" * 80)
    logger.info("[D92-1] Execution complete")
    logger.info("=" * 80)
    logger.info(f"Status: {result.get('status', 'unknown')}")
    logger.info(f"Run ID: {result.get('run_id', 'N/A')}")
    
    if result.get('status') == 'success':
        logger.info(f"Results: {result.get('log_dir', 'N/A')}")
        sys.exit(0)
    elif result.get('status') == 'dry_run':
        logger.info("Dry-run complete - no errors")
        sys.exit(0)
    else:
        logger.error(f"Execution failed: {result.get('error', 'unknown error')}")
        sys.exit(1)


if __name__ == "__main__":
    main()
