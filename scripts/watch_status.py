#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
D27 Real-time Status Monitor

Live/Paper/Tuning 상태를 실시간으로 모니터링하는 CLI 도구.
"""

import argparse
import os
import sys
import time
import logging
from datetime import datetime

# 프로젝트 경로 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from arbitrage.monitoring import LiveStatusMonitor, TuningStatusMonitor

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger(__name__)


def format_live_status(snapshot) -> str:
    """Live/Paper 상태를 포맷된 문자열로 변환"""
    lines = []
    lines.append("=" * 70)
    lines.append(f"[D27_MONITOR] LIVE/PAPER STATUS")
    lines.append("=" * 70)
    lines.append(f"Mode:                    {snapshot.mode.upper()}")
    lines.append(f"Environment:             {snapshot.env}")
    lines.append(f"Live Enabled:            {snapshot.live_enabled}")
    lines.append(f"Live Armed:              {snapshot.live_armed}")
    
    if snapshot.last_heartbeat:
        lines.append(f"Last Heartbeat:          {snapshot.last_heartbeat.isoformat()}")
    else:
        lines.append(f"Last Heartbeat:          (없음)")
    
    lines.append("")
    lines.append("--- Trades ---")
    if snapshot.trades_total is not None:
        lines.append(f"Total Trades:            {snapshot.trades_total}")
    if snapshot.trades_today is not None:
        lines.append(f"Trades Today:            {snapshot.trades_today}")
    
    lines.append("")
    lines.append("--- Safety ---")
    if snapshot.safety_violations_total is not None:
        lines.append(f"Safety Violations:       {snapshot.safety_violations_total}")
    if snapshot.circuit_breaker_triggers_total is not None:
        lines.append(f"Circuit Breaker Triggers: {snapshot.circuit_breaker_triggers_total}")
    
    lines.append("")
    lines.append("--- Portfolio ---")
    if snapshot.total_balance is not None:
        lines.append(f"Total Balance:           {snapshot.total_balance:,.2f}")
    if snapshot.available_balance is not None:
        lines.append(f"Available Balance:       {snapshot.available_balance:,.2f}")
    if snapshot.total_position_value is not None:
        lines.append(f"Total Position Value:    {snapshot.total_position_value:,.2f}")
    
    lines.append("")
    lines.append(f"Timestamp:               {snapshot.timestamp.isoformat()}")
    lines.append("=" * 70)
    
    return "\n".join(lines)


def format_tuning_status(snapshot) -> str:
    """튜닝 상태를 포맷된 문자열로 변환"""
    lines = []
    lines.append("=" * 70)
    lines.append(f"[D27_MONITOR] TUNING STATUS")
    lines.append("=" * 70)
    lines.append(f"Session ID:              {snapshot.session_id}")
    lines.append(f"Total Iterations:        {snapshot.total_iterations}")
    lines.append(f"Completed Iterations:    {snapshot.completed_iterations}")
    lines.append(f"Progress:                {snapshot.progress_pct:.1f}%")
    
    if snapshot.workers:
        lines.append(f"Workers:                 {', '.join(snapshot.workers)}")
    else:
        lines.append(f"Workers:                 (없음)")
    
    if snapshot.metrics_keys:
        lines.append(f"Metrics:                 {', '.join(snapshot.metrics_keys)}")
    else:
        lines.append(f"Metrics:                 (없음)")
    
    if snapshot.last_update:
        lines.append(f"Last Update:             {snapshot.last_update.isoformat()}")
    else:
        lines.append(f"Last Update:             (없음)")
    
    lines.append("")
    lines.append(f"Timestamp:               {snapshot.timestamp.isoformat()}")
    lines.append("=" * 70)
    
    return "\n".join(lines)


def print_status_once(target: str, **kwargs) -> bool:
    """한 번만 상태를 출력"""
    try:
        if target in ["live", "paper", "shadow"]:
            monitor = LiveStatusMonitor(
                mode=target,
                env=kwargs.get("env", "docker")
            )
            snapshot = monitor.load_snapshot()
            print(format_live_status(snapshot))
            return True
        
        elif target == "tuning":
            session_id = kwargs.get("session_id")
            if not session_id:
                logger.error("--session-id is required for tuning target")
                return False
            
            monitor = TuningStatusMonitor(
                session_id=session_id,
                total_iterations=kwargs.get("total_iterations", 0),
                env=kwargs.get("env", "docker"),
                mode=kwargs.get("mode", "paper")
            )
            snapshot = monitor.load_snapshot()
            print(format_tuning_status(snapshot))
            return True
        
        else:
            logger.error(f"Unknown target: {target}")
            return False
    
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        return False


def watch_status(target: str, interval: int, **kwargs) -> bool:
    """상태를 주기적으로 모니터링"""
    try:
        iteration = 0
        while True:
            iteration += 1
            
            # 화면 지우기 (터미널에서)
            if iteration > 1:
                print("\n" + "=" * 70)
                print(f"[D27_MONITOR] Refresh #{iteration} at {datetime.now().isoformat()}")
                print("=" * 70 + "\n")
            
            # 상태 출력
            if not print_status_once(target, **kwargs):
                return False
            
            # 대기
            logger.info(f"Next refresh in {interval} seconds... (Press CTRL+C to stop)")
            time.sleep(interval)
    
    except KeyboardInterrupt:
        logger.info("Monitoring stopped by user")
        return True
    except Exception as e:
        logger.error(f"Error during monitoring: {e}", exc_info=True)
        return False


def main():
    """메인 함수"""
    parser = argparse.ArgumentParser(
        description="D27 Real-time Status Monitor",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
예시:
  # Live 상태 한 번 조회
  python scripts/watch_status.py --target live --env docker
  
  # Paper 상태 5초마다 모니터링
  python scripts/watch_status.py --target paper --env docker --interval 5
  
  # 튜닝 세션 상태 한 번 조회
  python scripts/watch_status.py --target tuning --session-id <session-id> --total-iterations 5
  
  # 튜닝 세션 상태 3초마다 모니터링
  python scripts/watch_status.py --target tuning --session-id <session-id> --total-iterations 5 --interval 3
        """
    )
    
    parser.add_argument(
        "--target",
        required=True,
        choices=["live", "paper", "shadow", "tuning"],
        help="모니터링 대상 (live, paper, shadow, tuning)"
    )
    
    parser.add_argument(
        "--env",
        default="docker",
        choices=["docker", "local"],
        help="환경 (기본값: docker)"
    )
    
    parser.add_argument(
        "--mode",
        default="paper",
        choices=["paper", "shadow", "live"],
        help="튜닝 모드 (기본값: paper)"
    )
    
    parser.add_argument(
        "--session-id",
        default=None,
        help="튜닝 세션 ID (tuning 대상 필수)"
    )
    
    parser.add_argument(
        "--total-iterations",
        type=int,
        default=0,
        help="총 반복 수 (튜닝용, 기본값: 0)"
    )
    
    parser.add_argument(
        "--interval",
        type=int,
        default=None,
        help="갱신 주기 (초). 지정하면 무한 모니터링, 미지정하면 한 번만 조회"
    )
    
    args = parser.parse_args()
    
    try:
        kwargs = {
            "env": args.env,
            "mode": args.mode,
            "session_id": args.session_id,
            "total_iterations": args.total_iterations
        }
        
        if args.interval:
            # 무한 모니터링
            success = watch_status(args.target, args.interval, **kwargs)
        else:
            # 한 번만 조회
            success = print_status_once(args.target, **kwargs)
        
        return 0 if success else 1
    
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
