#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
D30 Kubernetes Job Validator

생성된 K8s Job YAML 파일을 검증하고 실행 계획을 생성.
실제 kubectl 실행 없음 (검증 및 분석만).
"""

import argparse
import os
import sys
import logging

# 프로젝트 경로 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from arbitrage.k8s_executor import (
    K8sJobValidator,
    K8sExecutionPlanner,
    generate_execution_plan_text
)

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """메인 함수"""
    parser = argparse.ArgumentParser(
        description="D30 Kubernetes Job Validator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
예시:
  # 기본 검증
  python scripts/validate_k8s_jobs.py --jobs-dir outputs/d29_k8s_jobs
  
  # 엄격한 검증 모드
  python scripts/validate_k8s_jobs.py --jobs-dir outputs/d29_k8s_jobs --strict
  
  # 실행 계획 파일로 저장
  python scripts/validate_k8s_jobs.py \
    --jobs-dir outputs/d29_k8s_jobs \
    --output-plan outputs/d30_execution_plan.txt
        """
    )
    
    parser.add_argument(
        "--jobs-dir",
        required=True,
        help="K8s Job YAML 파일 디렉토리"
    )
    
    parser.add_argument(
        "--strict",
        action="store_true",
        help="엄격한 검증 모드 (경고도 에러로 취급)"
    )
    
    parser.add_argument(
        "--output-plan",
        default=None,
        help="실행 계획 파일 저장 경로 (선택)"
    )
    
    args = parser.parse_args()
    
    try:
        logger.info(f"[D30_K8S_EXEC] Starting K8s Job validation")
        logger.info(f"[D30_K8S_EXEC] Jobs directory: {args.jobs_dir}")
        logger.info(f"[D30_K8S_EXEC] Strict mode: {args.strict}")
        
        # Validator 생성
        validator = K8sJobValidator(strict_mode=args.strict)
        
        # Planner 생성
        planner = K8sExecutionPlanner(validator)
        
        # 실행 계획 생성
        plan = planner.plan_from_directory(args.jobs_dir)
        
        # 실행 계획 텍스트 생성
        plan_text = generate_execution_plan_text(plan)
        
        # 콘솔에 출력
        print("\n" + plan_text + "\n")
        
        # 파일로 저장 (선택)
        if args.output_plan:
            with open(args.output_plan, 'w', encoding='utf-8') as f:
                f.write(plan_text)
            logger.info(f"[D30_K8S_EXEC] Execution plan saved: {args.output_plan}")
        
        # 종료 코드 결정
        if plan.invalid_jobs > 0:
            logger.warning(f"[D30_K8S_EXEC] {plan.invalid_jobs} invalid jobs found")
            return 1
        elif plan.errors:
            logger.error(f"[D30_K8S_EXEC] {len(plan.errors)} errors found")
            return 1
        elif args.strict and plan.warnings:
            logger.warning(f"[D30_K8S_EXEC] {len(plan.warnings)} warnings found (strict mode)")
            return 1
        else:
            logger.info(f"[D30_K8S_EXEC] All jobs validated successfully")
            return 0
    
    except Exception as e:
        logger.error(f"[D30_K8S_EXEC] Error: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
