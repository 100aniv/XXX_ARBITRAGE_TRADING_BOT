#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
D31 Safe Kubernetes Apply Layer CLI

생성된 K8s Job YAML 파일을 안전하게 K8s 클러스터에 적용.
기본값: dry-run 모드 (실제 kubectl 실행 안 함)
--apply 플래그로만 실제 실행
"""

import argparse
import os
import sys
import logging

# 프로젝트 경로 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from arbitrage.k8s_apply import (
    K8sApplyExecutor,
    generate_apply_report_text
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
        description="D31 Safe Kubernetes Apply Layer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
예시:
  # Dry-run 모드 (기본값, 실제 kubectl 실행 안 함)
  python scripts/apply_k8s_jobs.py --jobs-dir outputs/d29_k8s_jobs
  
  # 실제 적용 (--apply 플래그 필수)
  python scripts/apply_k8s_jobs.py \
    --jobs-dir outputs/d29_k8s_jobs \
    --apply
  
  # kubeconfig 지정
  python scripts/apply_k8s_jobs.py \
    --jobs-dir outputs/d29_k8s_jobs \
    --kubeconfig ~/.kube/config \
    --context my-cluster \
    --apply
  
  # 결과 파일로 저장
  python scripts/apply_k8s_jobs.py \
    --jobs-dir outputs/d29_k8s_jobs \
    --apply \
    --output-report outputs/d31_apply_report.txt
        """
    )
    
    parser.add_argument(
        "--jobs-dir",
        required=True,
        help="K8s Job YAML 파일 디렉토리"
    )
    
    parser.add_argument(
        "--kubeconfig",
        default=None,
        help="kubeconfig 파일 경로 (선택)"
    )
    
    parser.add_argument(
        "--context",
        default=None,
        help="K8s 컨텍스트 (선택)"
    )
    
    parser.add_argument(
        "--apply",
        action="store_true",
        help="실제 kubectl apply 실행 (기본값: dry-run)"
    )
    
    parser.add_argument(
        "--output-report",
        default=None,
        help="Apply 결과 보고서 파일 저장 경로 (선택)"
    )
    
    args = parser.parse_args()
    
    try:
        logger.info(f"[D31_K8S_APPLY] Starting K8s Apply Layer")
        logger.info(f"[D31_K8S_APPLY] Jobs directory: {args.jobs_dir}")
        logger.info(f"[D31_K8S_APPLY] Mode: {'APPLY' if args.apply else 'DRY-RUN'}")
        
        if args.apply:
            logger.warning(f"[D31_K8S_APPLY] ⚠️  APPLY MODE ENABLED - kubectl will be executed")
        
        # Executor 생성
        executor = K8sApplyExecutor(
            dry_run=not args.apply,
            kubeconfig=args.kubeconfig,
            context=args.context
        )
        
        # Apply 계획 생성
        plan = executor.build_plan(args.jobs_dir)
        
        # Apply 계획 실행
        result = executor.execute_plan(plan)
        
        # Apply 결과 텍스트 생성
        report_text = generate_apply_report_text(result)
        
        # 콘솔에 출력
        print("\n" + report_text + "\n")
        
        # 파일로 저장 (선택)
        if args.output_report:
            with open(args.output_report, 'w', encoding='utf-8') as f:
                f.write(report_text)
            logger.info(f"[D31_K8S_APPLY] Apply report saved: {args.output_report}")
        
        # 종료 코드 결정
        if result.failed_jobs > 0:
            logger.error(f"[D31_K8S_APPLY] {result.failed_jobs} jobs failed")
            return 1
        else:
            logger.info(f"[D31_K8S_APPLY] All jobs processed successfully")
            return 0
    
    except Exception as e:
        logger.error(f"[D31_K8S_APPLY] Error: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
