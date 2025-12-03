#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
D77-0-RM-EXT: Real Market 1h+ Extended PAPER Validation Runner

기존 run_d77_0_topn_arbitrage_paper.py를 호출하는 간단한 래퍼.
Preset 시나리오를 제공하여 사용 편의성 향상.

Usage:
    # Smoke Test (3분)
    python scripts/run_d77_0_rm_ext.py --scenario smoke
    
    # Primary Scenario (1시간, Top20)
    python scripts/run_d77_0_rm_ext.py --scenario primary
    
    # Extended Scenario (1시간, Top50)
    python scripts/run_d77_0_rm_ext.py --scenario extended
    
    # Custom
    python scripts/run_d77_0_rm_ext.py --scenario custom --universe top20 --duration-minutes 120
"""

import argparse
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# 프로젝트 루트
PROJECT_ROOT = Path(__file__).parent.parent
RUNNER_SCRIPT = PROJECT_ROOT / "scripts" / "run_d77_0_topn_arbitrage_paper.py"


def main():
    parser = argparse.ArgumentParser(
        description="D77-0-RM-EXT: Real Market 1h+ Extended PAPER Validation Runner"
    )
    parser.add_argument(
        "--scenario",
        type=str,
        choices=["smoke", "primary", "extended", "custom"],
        default="primary",
        help="실행 시나리오 (smoke=3m, primary=1h Top20, extended=1h Top50, custom=커스텀)"
    )
    parser.add_argument(
        "--universe",
        type=str,
        choices=["top10", "top20", "top50", "top100"],
        help="Custom 시나리오 시 Universe 크기"
    )
    parser.add_argument(
        "--duration-minutes",
        type=int,
        help="Custom 시나리오 시 실행 시간 (분)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="실제 실행 없이 명령어만 출력"
    )
    
    args = parser.parse_args()
    
    # Scenario별 preset 설정
    if args.scenario == "smoke":
        universe = "top20"
        duration_minutes = 3
        output_suffix = "smoke_3m"
    elif args.scenario == "primary":
        universe = "top20"
        duration_minutes = 60
        output_suffix = "1h_top20"
    elif args.scenario == "extended":
        universe = "top50"
        duration_minutes = 60
        output_suffix = "1h_top50"
    elif args.scenario == "custom":
        if not args.universe or not args.duration_minutes:
            print("[ERROR] --scenario custom 시 --universe와 --duration-minutes 필수")
            sys.exit(1)
        universe = args.universe
        duration_minutes = args.duration_minutes
        output_suffix = f"{duration_minutes}m_{universe}"
    else:
        print(f"[ERROR] 알 수 없는 시나리오: {args.scenario}")
        sys.exit(1)
    
    # 출력 디렉토리 및 파일 경로 생성
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_id = f"run_{timestamp}"
    log_dir = PROJECT_ROOT / "logs" / "d77-0-rm-ext" / run_id
    log_dir.mkdir(parents=True, exist_ok=True)
    
    kpi_output_path = log_dir / f"{output_suffix}_kpi.json"
    
    # 실행 명령어 구성
    cmd = [
        sys.executable,  # python 인터프리터
        str(RUNNER_SCRIPT),
        "--universe", universe,
        "--duration-minutes", str(duration_minutes),
        "--data-source", "real",
        "--monitoring-enabled",
        "--kpi-output-path", str(kpi_output_path)
    ]
    
    # 명령어 출력
    print("="*80)
    print(f"[D77-0-RM-EXT] {args.scenario.upper()} Scenario")
    print("="*80)
    print(f"Universe: {universe}")
    print(f"Duration: {duration_minutes} minutes")
    print(f"Run ID: {run_id}")
    print(f"Log Dir: {log_dir}")
    print(f"KPI Output: {kpi_output_path}")
    print(f"\nCommand:")
    print(" ".join(cmd))
    print("="*80)
    
    if args.dry_run:
        print("\n[DRY-RUN] 실제 실행하지 않음.")
        return 0
    
    # 실행
    print("\n[INFO] 실행 시작...")
    try:
        result = subprocess.run(cmd, check=True)
        print(f"\n[OK] 실행 완료 (Exit Code: {result.returncode})")
        print(f"[INFO] KPI 파일: {kpi_output_path}")
        return result.returncode
    except subprocess.CalledProcessError as e:
        print(f"\n[ERROR] 실행 실패 (Exit Code: {e.returncode})")
        return e.returncode
    except KeyboardInterrupt:
        print("\n[WARNING] 사용자 중단 (Ctrl+C)")
        return 130


if __name__ == "__main__":
    sys.exit(main())
