#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
D34 Record Kubernetes Health & Events

K8s 건강 상태를 평가하고 히스토리에 기록합니다.
"""

import argparse
import os
import sys
import logging

# 프로젝트 경로 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from arbitrage.k8s_monitor import K8sJobMonitor
from arbitrage.k8s_health import K8sHealthEvaluator
from arbitrage.k8s_history import K8sHealthHistoryStore

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """메인 함수"""
    parser = argparse.ArgumentParser(
        description="D34 Record Kubernetes Health & Events",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
예시:
  # 기본 사용
  python scripts/record_k8s_health.py \
    --namespace trading-bots \
    --label-selector app=arbitrage-tuning,session_id=d29-k8s-demo-session \
    --history-file outputs/k8s_health_history.jsonl
  
  # kubeconfig 지정
  python scripts/record_k8s_health.py \
    --namespace trading-bots \
    --label-selector app=arbitrage-tuning \
    --kubeconfig ~/.kube/config \
    --context my-cluster \
    --history-file outputs/k8s_health_history.jsonl
  
  # Strict 모드
  python scripts/record_k8s_health.py \
    --namespace trading-bots \
    --label-selector app=arbitrage-tuning \
    --history-file outputs/k8s_health_history.jsonl \
    --strict

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
        "--history-file",
        required=True,
        help="히스토리 파일 경로 (예: outputs/k8s_health_history.jsonl)"
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
    
    args = parser.parse_args()
    
    try:
        logger.info(f"[D34_RECORD] Starting K8s Health Recording")
        logger.info(f"[D34_RECORD] Namespace: {args.namespace}")
        logger.info(f"[D34_RECORD] Label Selector: {args.label_selector}")
        logger.info(f"[D34_RECORD] History File: {args.history_file}")
        logger.info(f"[D34_RECORD] Strict Mode: {args.strict}")
        
        # Monitor 생성 (D32)
        monitor = K8sJobMonitor(
            namespace=args.namespace,
            label_selector=args.label_selector,
            kubeconfig=args.kubeconfig,
            context=args.context,
            max_log_lines=args.max_log_lines
        )
        
        # 스냅샷 로드
        logger.info(f"[D34_RECORD] Loading monitoring snapshot...")
        snapshot = monitor.load_snapshot()
        
        # 건강 상태 평가 (D33)
        logger.info(f"[D34_RECORD] Evaluating health...")
        evaluator = K8sHealthEvaluator(
            warn_on_pending=True,
            treat_unknown_as_error=True
        )
        health = evaluator.evaluate(snapshot)
        
        # 히스토리에 기록 (D34)
        logger.info(f"[D34_RECORD] Recording to history...")
        store = K8sHealthHistoryStore(args.history_file)
        record = store.append(health)
        
        # 요약 출력
        print("\n" + "="*80)
        print("[D34_RECORD] HEALTH RECORD SUMMARY")
        print("="*80)
        print(f"\nNamespace:               {health.namespace}")
        print(f"Label Selector:          {health.selector}")
        print(f"Timestamp:               {health.timestamp}")
        print(f"Overall Health:          {health.overall_health}")
        print(f"\nJob Counts:")
        print(f"  OK:                    {record.jobs_ok}")
        print(f"  WARN:                  {record.jobs_warn}")
        print(f"  ERROR:                 {record.jobs_error}")
        print(f"\nHistory File:            {args.history_file}")
        print("="*80 + "\n")
        
        # 종료 코드 결정
        exit_code = _determine_exit_code(health.overall_health, args.strict)
        logger.info(f"[D34_RECORD] Health record complete: {health.overall_health} (exit code: {exit_code})")
        
        return exit_code
    
    except Exception as e:
        logger.error(f"[D34_RECORD] Error: {e}", exc_info=True)
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
