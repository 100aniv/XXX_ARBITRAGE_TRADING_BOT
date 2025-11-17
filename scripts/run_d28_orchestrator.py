#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
D28 Tuning Orchestrator CLI

분산 / 병렬 튜닝 세션을 관리하는 Orchestrator.
"""

import argparse
import os
import sys
import yaml
import logging
from datetime import datetime

# 프로젝트 경로 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from arbitrage.tuning_orchestrator import (
    TuningOrchestrator,
    OrchestratorConfig,
    JobStatus
)

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger(__name__)


def load_config(config_path: str) -> OrchestratorConfig:
    """설정 파일 로드"""
    with open(config_path, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)
    
    return OrchestratorConfig(**data)


def print_summary(orchestrator: TuningOrchestrator) -> None:
    """Orchestrator 실행 요약 출력"""
    summary = orchestrator.get_summary()
    
    print("\n" + "=" * 70)
    print("[D28_ORCH] ORCHESTRATION SUMMARY")
    print("=" * 70)
    print(f"Session ID:              {summary['session_id']}")
    print(f"Total Jobs:              {summary['total_jobs']}")
    print(f"Success Jobs:            {summary['success_jobs']}")
    print(f"Failed Jobs:             {summary['failed_jobs']}")
    print(f"Total Iterations:        {summary['total_iterations']}")
    print(f"Workers:                 {summary['workers']}")
    print(f"Mode:                    {summary['mode']}")
    print(f"Environment:             {summary['env']}")
    print(f"Optimizer:               {summary['optimizer']}")
    print("=" * 70 + "\n")


def main():
    """메인 함수"""
    parser = argparse.ArgumentParser(
        description="D28 Tuning Orchestrator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
예시:
  # 기본 설정 파일로 실행
  python scripts/run_d28_orchestrator.py --config configs/d28_orchestrator/demo_baseline.yaml
  
  # 설정 파일 + 옵션 오버라이드
  python scripts/run_d28_orchestrator.py \
    --config configs/d28_orchestrator/demo_baseline.yaml \
    --workers 3 \
    --total-iterations 9
        """
    )
    
    parser.add_argument(
        "--config",
        required=True,
        help="Orchestrator 설정 파일 경로"
    )
    
    parser.add_argument(
        "--session-id",
        default=None,
        help="세션 ID (설정 파일 오버라이드)"
    )
    
    parser.add_argument(
        "--total-iterations",
        type=int,
        default=None,
        help="총 반복 수 (설정 파일 오버라이드)"
    )
    
    parser.add_argument(
        "--workers",
        type=int,
        default=None,
        help="워커 수 (설정 파일 오버라이드)"
    )
    
    parser.add_argument(
        "--mode",
        default=None,
        choices=["paper", "shadow", "live"],
        help="모드 (설정 파일 오버라이드)"
    )
    
    parser.add_argument(
        "--env",
        default=None,
        choices=["docker", "local"],
        help="환경 (설정 파일 오버라이드)"
    )
    
    parser.add_argument(
        "--optimizer",
        default=None,
        choices=["bayesian", "grid", "random"],
        help="Optimizer (설정 파일 오버라이드)"
    )
    
    args = parser.parse_args()
    
    try:
        # 설정 로드
        logger.info(f"Loading config from: {args.config}")
        config = load_config(args.config)
        
        # 옵션 오버라이드
        if args.session_id:
            config.session_id = args.session_id
        if args.total_iterations:
            config.total_iterations = args.total_iterations
        if args.workers:
            config.workers = args.workers
        if args.mode:
            config.mode = args.mode
        if args.env:
            config.env = args.env
        if args.optimizer:
            config.optimizer = args.optimizer
        
        # Orchestrator 생성
        orchestrator = TuningOrchestrator(config)
        
        # Job 계획
        logger.info("[D28_ORCH] Planning jobs...")
        jobs = orchestrator.plan_jobs()
        
        print("\n" + "=" * 70)
        print("[D28_ORCH] JOB PLAN")
        print("=" * 70)
        for job in jobs:
            print(f"  {job.worker_id}: {job.iterations} iterations")
        print("=" * 70 + "\n")
        
        # 모든 Job 실행
        logger.info("[D28_ORCH] Running all jobs...")
        success = orchestrator.run_all()
        
        # 요약 출력
        print_summary(orchestrator)
        
        return 0 if success else 1
    
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
