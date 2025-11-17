#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
D33 Kubernetes Health Evaluation & CI-friendly Alert Layer CLI

K8s Job/Pod 건강 상태를 평가하고 CI/CD 친화적인 종료 코드를 제공합니다.
"""

import argparse
import os
import sys
import logging
import json

# 프로젝트 경로 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from arbitrage.k8s_monitor import K8sJobMonitor
from arbitrage.k8s_health import (
    K8sHealthEvaluator,
    generate_health_report_text
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
        description="D33 Kubernetes Health Evaluation & CI-friendly Alerts",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
예시:
  # 한 번만 건강 상태 확인
  python scripts/check_k8s_health.py \
    --namespace trading-bots \
    --label-selector app=arbitrage-tuning,session_id=d29-k8s-demo-session
  
  # Strict 모드 (WARN도 에러로 처리)
  python scripts/check_k8s_health.py \
    --namespace trading-bots \
    --label-selector app=arbitrage-tuning \
    --strict
  
  # kubeconfig 지정
  python scripts/check_k8s_health.py \
    --namespace trading-bots \
    --label-selector app=arbitrage-tuning \
    --kubeconfig ~/.kube/config \
    --context my-cluster
  
  # JSON 출력 저장
  python scripts/check_k8s_health.py \
    --namespace trading-bots \
    --label-selector app=arbitrage-tuning \
    --output-json health_report.json

종료 코드:
  0: OK (또는 WARN with --strict 미설정)
  1: WARN (with --strict)
  2: ERROR
        """
    )
    
    parser.add_argument(
        "--namespace",
        required=True,
        help="K8s 네임스페이스 (예: trading-bots)"
    )
    
    parser.add_argument(
        "--label-selector",
        required=True,
        help="레이블 선택자 (예: app=arbitrage-tuning,session_id=...)"
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
        "--strict",
        action="store_true",
        help="Strict 모드: WARN도 에러로 처리 (종료 코드 1)"
    )
    
    parser.add_argument(
        "--max-log-lines",
        type=int,
        default=100,
        help="Pod당 최대 로그 라인 수 (기본값: 100)"
    )
    
    parser.add_argument(
        "--output-json",
        default=None,
        help="JSON 형식의 건강 상태 보고서를 파일로 저장"
    )
    
    args = parser.parse_args()
    
    try:
        logger.info(f"[D33_K8S_HEALTH] Starting K8s Health Evaluation")
        logger.info(f"[D33_K8S_HEALTH] Namespace: {args.namespace}")
        logger.info(f"[D33_K8S_HEALTH] Label Selector: {args.label_selector}")
        logger.info(f"[D33_K8S_HEALTH] Strict Mode: {args.strict}")
        
        # Monitor 생성 (D32)
        monitor = K8sJobMonitor(
            namespace=args.namespace,
            label_selector=args.label_selector,
            kubeconfig=args.kubeconfig,
            context=args.context,
            max_log_lines=args.max_log_lines
        )
        
        # 스냅샷 로드
        logger.info(f"[D33_K8S_HEALTH] Loading monitoring snapshot...")
        snapshot = monitor.load_snapshot()
        
        # 건강 상태 평가 (D33)
        logger.info(f"[D33_K8S_HEALTH] Evaluating health...")
        evaluator = K8sHealthEvaluator(
            warn_on_pending=True,
            treat_unknown_as_error=True
        )
        health = evaluator.evaluate(snapshot)
        
        # 텍스트 보고서 출력
        report_text = generate_health_report_text(health)
        print("\n" + report_text + "\n")
        
        # JSON 출력 (선택)
        if args.output_json:
            logger.info(f"[D33_K8S_HEALTH] Writing JSON report to {args.output_json}")
            json_report = {
                "namespace": health.namespace,
                "selector": health.selector,
                "overall_health": health.overall_health,
                "timestamp": health.timestamp,
                "jobs_health": [
                    {
                        "job_name": jh.job_name,
                        "namespace": jh.namespace,
                        "phase": jh.phase,
                        "health": jh.health,
                        "reasons": jh.reasons,
                        "succeeded": jh.succeeded,
                        "failed": jh.failed,
                        "active": jh.active,
                        "labels": jh.labels
                    }
                    for jh in health.jobs_health
                ],
                "errors": health.errors
            }
            
            with open(args.output_json, 'w', encoding='utf-8') as f:
                json.dump(json_report, f, indent=2, ensure_ascii=False)
            
            logger.info(f"[D33_K8S_HEALTH] JSON report written successfully")
        
        # 종료 코드 결정
        exit_code = _determine_exit_code(health.overall_health, args.strict)
        logger.info(f"[D33_K8S_HEALTH] Health check complete: {health.overall_health} (exit code: {exit_code})")
        
        return exit_code
    
    except Exception as e:
        logger.error(f"[D33_K8S_HEALTH] Error: {e}", exc_info=True)
        return 2


def _determine_exit_code(overall_health: str, strict: bool) -> int:
    """
    종료 코드 결정
    
    Args:
        overall_health: "OK", "WARN", "ERROR"
        strict: Strict 모드 여부
    
    Returns:
        종료 코드 (0, 1, 2)
    """
    if overall_health == "OK":
        return 0
    elif overall_health == "WARN":
        return 1 if strict else 0
    elif overall_health == "ERROR":
        return 2
    else:
        # 예상치 못한 상태
        return 2


if __name__ == "__main__":
    sys.exit(main())
