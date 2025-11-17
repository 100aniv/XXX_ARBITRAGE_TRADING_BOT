#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
D32 Kubernetes Job/Pod Monitoring & Log Collection CLI

K8s 클러스터의 Job/Pod 상태 모니터링 및 로그 수집.
실제 kubectl get/logs 호출로 정보 수집 (수정 작업 없음).
"""

import argparse
import os
import sys
import logging
import time

# 프로젝트 경로 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from arbitrage.k8s_monitor import (
    K8sJobMonitor,
    generate_monitor_report_text
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
        description="D32 Kubernetes Job/Pod Monitoring & Log Collection",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
예시:
  # 한 번만 상태 확인
  python scripts/watch_k8s_jobs.py \
    --namespace trading-bots \
    --label-selector app=arbitrage-tuning,session_id=d29-k8s-demo-session
  
  # 5초마다 상태 갱신 (watch 모드)
  python scripts/watch_k8s_jobs.py \
    --namespace trading-bots \
    --label-selector app=arbitrage-tuning,session_id=d29-k8s-demo-session \
    --interval 5
  
  # kubeconfig 지정
  python scripts/watch_k8s_jobs.py \
    --namespace trading-bots \
    --label-selector app=arbitrage-tuning \
    --kubeconfig ~/.kube/config \
    --context my-cluster \
    --interval 5
  
  # 로그 라인 수 조정
  python scripts/watch_k8s_jobs.py \
    --namespace trading-bots \
    --label-selector app=arbitrage-tuning \
    --max-log-lines 50 \
    --interval 5
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
        "--interval",
        type=int,
        default=None,
        help="갱신 간격 (초) - 없으면 한 번만 실행"
    )
    
    parser.add_argument(
        "--max-log-lines",
        type=int,
        default=100,
        help="Pod당 최대 로그 라인 수 (기본값: 100)"
    )
    
    args = parser.parse_args()
    
    try:
        logger.info(f"[D32_K8S_MONITOR] Starting K8s Job/Pod Monitoring")
        logger.info(f"[D32_K8S_MONITOR] Namespace: {args.namespace}")
        logger.info(f"[D32_K8S_MONITOR] Label Selector: {args.label_selector}")
        
        if args.interval:
            logger.info(f"[D32_K8S_MONITOR] Watch mode: interval={args.interval}s")
        else:
            logger.info(f"[D32_K8S_MONITOR] One-shot mode")
        
        # Monitor 생성
        monitor = K8sJobMonitor(
            namespace=args.namespace,
            label_selector=args.label_selector,
            kubeconfig=args.kubeconfig,
            context=args.context,
            max_log_lines=args.max_log_lines
        )
        
        if args.interval:
            # Watch 모드
            iteration = 0
            try:
                while True:
                    iteration += 1
                    logger.info(f"[D32_K8S_MONITOR] Iteration {iteration}")
                    
                    # 스냅샷 로드
                    snapshot = monitor.load_snapshot()
                    
                    # 보고서 생성 및 출력
                    report_text = generate_monitor_report_text(snapshot)
                    print("\n" + report_text + "\n")
                    
                    # 다음 갱신까지 대기
                    logger.info(f"[D32_K8S_MONITOR] Waiting {args.interval}s for next update...")
                    time.sleep(args.interval)
            
            except KeyboardInterrupt:
                logger.info(f"[D32_K8S_MONITOR] Watch mode interrupted by user")
                return 0
        
        else:
            # One-shot 모드
            snapshot = monitor.load_snapshot()
            
            # 보고서 생성 및 출력
            report_text = generate_monitor_report_text(snapshot)
            print("\n" + report_text + "\n")
            
            logger.info(f"[D32_K8S_MONITOR] Monitoring complete")
        
        return 0
    
    except Exception as e:
        logger.error(f"[D32_K8S_MONITOR] Error: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
