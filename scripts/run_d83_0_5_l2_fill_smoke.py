#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
D83-0.5: L2 Fill Model PAPER Smoke Test (5~10분)

목적:
- D83-0 L2 Orderbook Integration 실전 검증
- D84-1 Fill Model Infrastructure 실전 검증
- FillEventCollector로 Fill 이벤트 수집
- available_volume 및 fill_ratio 실시간 변동 확인

실행 조건:
- FILL_MODEL_ENABLE=true (필수)
- L2 Orderbook Provider 활성화
- FillEventCollector 활성화

Usage:
    python scripts/run_d83_0_5_l2_fill_smoke.py --duration-minutes 5
    python scripts/run_d83_0_5_l2_fill_smoke.py --duration-minutes 10 --symbol BTC
"""

import argparse
import asyncio
import json
import logging
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any

# 프로젝트 루트 추가
sys.path.insert(0, str(Path(__file__).parent.parent))

# D83-0.5: Import 추가
from arbitrage.metrics.fill_stats import FillEventCollector
from arbitrage.exchanges.market_data_provider import WebSocketMarketDataProvider

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def kill_existing_processes():
    """기존 PAPER 프로세스 종료"""
    logger.info("[D83-0.5] Killing existing PAPER processes...")
    
    try:
        import psutil
        current_pid = os.getpid()
        killed_count = 0
        
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                if proc.info['pid'] == current_pid:
                    continue
                
                if proc.info['name'] and 'python' in proc.info['name'].lower():
                    cmdline = proc.info.get('cmdline', [])
                    if not cmdline:
                        continue
                    
                    cmdline_str = ' '.join(str(arg) for arg in cmdline)
                    
                    # Skip this script
                    if 'd83_0_5' in cmdline_str:
                        continue
                    
                    # Kill PAPER-related processes
                    if 'run_d77' in cmdline_str or 'run_d82' in cmdline_str or 'paper' in cmdline_str.lower():
                        logger.info(f"Killing process {proc.info['pid']}: {' '.join(cmdline[:3])}")
                        proc.kill()
                        killed_count += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        
        if killed_count > 0:
            logger.info(f"[D83-0.5] Killed {killed_count} processes")
        else:
            logger.info("[D83-0.5] No processes to kill")
            
    except Exception as e:
        logger.warning(f"[D83-0.5] Failed to kill processes: {e}")


def check_docker_services() -> bool:
    """Docker 서비스 확인"""
    logger.info("[D83-0.5] Checking Docker services...")
    
    try:
        result = subprocess.run(
            ["docker", "ps"],
            capture_output=True,
            text=True,
            check=False,
            encoding='utf-8',
            errors='replace',
        )
        
        if result.returncode != 0:
            logger.error("[D83-0.5] Docker is not running!")
            return False
        
        # Redis/Postgres/Prometheus 확인
        required_services = ["redis", "postgres", "prometheus"]
        for service in required_services:
            if service not in result.stdout.lower():
                logger.warning(f"[D83-0.5] Service not running: {service}")
        
        logger.info("[D83-0.5] Docker services OK")
        return True
            
    except Exception as e:
        logger.error(f"[D83-0.5] Docker check failed: {e}")
        return False


def run_smoke_test(duration_minutes: int, symbol: str = "BTC") -> Dict[str, Any]:
    """
    D83-0.5 PAPER 스모크 테스트 실행
    
    기존 run_d77_0_topn_arbitrage_paper.py를 사용하되,
    단일 심볼 + FillEventCollector 활성화로 실행
    
    Args:
        duration_minutes: 실행 시간 (분)
        symbol: 거래 심볼 (기본: BTC)
    
    Returns:
        실행 결과 요약
    """
    logger.info(f"[D83-0.5] Starting PAPER smoke test (duration={duration_minutes}min, symbol={symbol})")
    
    # D83-0.5: 환경변수 설정
    env = os.environ.copy()
    env["FILL_MODEL_ENABLE"] = "true"
    env["ARBITRAGE_ENV"] = "paper"
    
    # D83-0.5: FillEventCollector 출력 경로
    session_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    output_dir = Path("logs/d83-0.5")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    fill_events_path = output_dir / f"fill_events_{session_id}.jsonl"
    kpi_path = output_dir / f"kpi_{session_id}.json"
    
    # D83-0.5: 기존 runner 호출 (TopN 20, real data)
    cmd = [
        sys.executable,
        "scripts/run_d77_0_topn_arbitrage_paper.py",
        "--universe", "top20",
        "--duration-minutes", str(duration_minutes),
        "--data-source", "real",
        "--monitoring-enabled",
        "--kpi-output-path", str(kpi_path),
    ]
    
    logger.info(f"[D83-0.5] Command: {' '.join(cmd)}")
    logger.info(f"[D83-0.5] Fill events output: {fill_events_path}")
    logger.info(f"[D83-0.5] KPI output: {kpi_path}")
    
    # 실행
    try:
        result = subprocess.run(
            cmd,
            env=env,
            capture_output=True,
            text=True,
            check=False,
            encoding='utf-8',
            errors='replace',
        )
        
        # 로그 출력
        logger.info("[D83-0.5] ===== STDOUT =====")
        for line in result.stdout.splitlines()[-50:]:  # 마지막 50줄
            logger.info(line)
        
        if result.stderr:
            logger.warning("[D83-0.5] ===== STDERR =====")
            for line in result.stderr.splitlines()[-20:]:  # 마지막 20줄
                logger.warning(line)
        
        # KPI 파일 로드
        if kpi_path.exists():
            with open(kpi_path, "r") as f:
                kpi = json.load(f)
            logger.info(f"[D83-0.5] KPI loaded: {len(kpi)} metrics")
            return kpi
        else:
            logger.error(f"[D83-0.5] KPI file not found: {kpi_path}")
            return {}
            
    except Exception as e:
        logger.error(f"[D83-0.5] Smoke test failed: {e}")
        return {}


def main():
    """D83-0.5 실행"""
    parser = argparse.ArgumentParser(description="D83-0.5: L2 Fill Model PAPER Smoke Test")
    parser.add_argument(
        "--duration-minutes",
        type=int,
        default=5,
        help="실행 시간 (분, 기본: 5)",
    )
    parser.add_argument(
        "--symbol",
        type=str,
        default="BTC",
        help="거래 심볼 (기본: BTC)",
    )
    parser.add_argument(
        "--skip-env-check",
        action="store_true",
        help="환경 체크 건너뛰기",
    )
    
    args = parser.parse_args()
    
    logger.info("=" * 80)
    logger.info("[D83-0.5] L2 Fill Model PAPER Smoke Test")
    logger.info("=" * 80)
    logger.info(f"Duration: {args.duration_minutes} minutes")
    logger.info(f"Symbol: {args.symbol}")
    logger.info("")
    
    # 1. 환경 정리
    if not args.skip_env_check:
        kill_existing_processes()
        if not check_docker_services():
            logger.error("[D83-0.5] Docker services not ready. Exiting.")
            sys.exit(1)
    
    # 2. PAPER 실행
    kpi = run_smoke_test(args.duration_minutes, args.symbol)
    
    # 3. 결과 요약
    if kpi:
        logger.info("")
        logger.info("=" * 80)
        logger.info("[D83-0.5] Summary")
        logger.info("=" * 80)
        logger.info(f"Entry Trades: {kpi.get('entry_trades', 0)}")
        logger.info(f"Exit Trades: {kpi.get('exit_trades', 0)}")
        logger.info(f"Round Trips: {kpi.get('round_trips_completed', 0)}")
        logger.info(f"Win Rate: {kpi.get('win_rate_pct', 0):.1f}%")
        logger.info(f"Total PnL: ${kpi.get('total_pnl_usd', 0):.2f}")
        logger.info(f"Avg Buy Fill Ratio: {kpi.get('avg_buy_fill_ratio', 0):.2%}")
        logger.info(f"Avg Sell Fill Ratio: {kpi.get('avg_sell_fill_ratio', 0):.2%}")
        logger.info(f"Avg Buy Slippage: {kpi.get('avg_buy_slippage_bps', 0):.2f} bps")
        logger.info(f"Avg Sell Slippage: {kpi.get('avg_sell_slippage_bps', 0):.2f} bps")
        logger.info("=" * 80)
        
        # D83-0.5: Fill Event 분석은 별도 스크립트로
        logger.info("")
        logger.info("[D83-0.5] Next: Analyze fill events with scripts/analyze_d83_0_5_fill_events.py")
    else:
        logger.error("[D83-0.5] No KPI data available")
        sys.exit(1)


if __name__ == "__main__":
    main()
