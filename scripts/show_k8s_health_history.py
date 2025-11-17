#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
D34 Show Kubernetes Health History

저장된 건강 상태 히스토리를 조회합니다.
"""

import argparse
import os
import sys
import logging

# 프로젝트 경로 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

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
        description="D34 Show Kubernetes Health History",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
예시:
  # 최근 20개 레코드 표시
  python scripts/show_k8s_health_history.py \
    --history-file outputs/k8s_health_history.jsonl \
    --limit 20
  
  # 요약만 표시
  python scripts/show_k8s_health_history.py \
    --history-file outputs/k8s_health_history.jsonl \
    --summary-only
  
  # 최근 50개 레코드 표시
  python scripts/show_k8s_health_history.py \
    --history-file outputs/k8s_health_history.jsonl \
    --limit 50
        """
    )
    
    parser.add_argument(
        "--history-file",
        required=True,
        help="히스토리 파일 경로 (예: outputs/k8s_health_history.jsonl)"
    )
    
    parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="표시할 최대 레코드 수 (기본값: 20)"
    )
    
    parser.add_argument(
        "--summary-only",
        action="store_true",
        help="요약만 표시"
    )
    
    args = parser.parse_args()
    
    try:
        logger.info(f"[D34_SHOW] Loading history from {args.history_file}")
        
        store = K8sHealthHistoryStore(args.history_file)
        
        if args.summary_only:
            # 요약 표시
            summary = store.summarize()
            _print_summary(summary)
        else:
            # 최근 레코드 표시
            records = store.load_recent(limit=args.limit)
            _print_records(records)
        
        return 0
    
    except Exception as e:
        logger.error(f"[D34_SHOW] Error: {e}", exc_info=True)
        return 1


def _print_summary(summary: dict) -> None:
    """요약 출력"""
    print("\n" + "="*80)
    print("[D34_SHOW] KUBERNETES HEALTH HISTORY SUMMARY")
    print("="*80)
    print(f"\nTotal Records:           {summary.get('total_records', 0)}")
    print(f"\nHealth Status Counts:")
    print(f"  OK:                    {summary.get('ok_count', 0)}")
    print(f"  WARN:                  {summary.get('warn_count', 0)}")
    print(f"  ERROR:                 {summary.get('error_count', 0)}")
    print(f"\nLast Record:")
    print(f"  Overall Health:        {summary.get('last_overall_health', 'N/A')}")
    print(f"  Timestamp:             {summary.get('last_timestamp', 'N/A')}")
    print(f"  Jobs OK:               {summary.get('last_jobs_ok', 0)}")
    print(f"  Jobs WARN:             {summary.get('last_jobs_warn', 0)}")
    print(f"  Jobs ERROR:            {summary.get('last_jobs_error', 0)}")
    print("="*80 + "\n")


def _print_records(records: list) -> None:
    """레코드 목록 출력"""
    if not records:
        print("\n" + "="*80)
        print("[D34_SHOW] No records found")
        print("="*80 + "\n")
        return
    
    print("\n" + "="*80)
    print("[D34_SHOW] KUBERNETES HEALTH HISTORY RECORDS")
    print("="*80)
    print(f"\nTotal Records: {len(records)}\n")
    
    # 헤더
    print(f"{'#':<3} {'Timestamp':<26} {'Health':<8} {'OK':<3} {'WARN':<4} {'ERR':<3} {'Namespace':<15} {'Selector':<30}")
    print("-" * 100)
    
    # 레코드
    for i, record in enumerate(records, 1):
        # 선택자 단축
        selector = record.selector
        if len(selector) > 30:
            selector = selector[:27] + "..."
        
        print(
            f"{i:<3} {record.timestamp:<26} {record.overall_health:<8} "
            f"{record.jobs_ok:<3} {record.jobs_warn:<4} {record.jobs_error:<3} "
            f"{record.namespace:<15} {selector:<30}"
        )
    
    print("="*80 + "\n")


if __name__ == "__main__":
    sys.exit(main())
