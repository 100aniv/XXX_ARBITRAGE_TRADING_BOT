#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
D26 Tuning Result Summary & Analyzer

CSV 파일에서 튜닝 결과를 로드하여 요약/랭킹 출력.
"""

import argparse
import os
import sys
import logging

# 프로젝트 경로 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from arbitrage.tuning_analysis import (
    load_results_from_csv,
    TuningAnalyzer,
    format_result_summary
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
        description="D26 Tuning Result Summary & Analyzer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
예시:
  # 기본 요약
  python scripts/show_tuning_summary.py --csv outputs/d24_tuning_session.csv
  
  # PnL 기준 상위 5개
  python scripts/show_tuning_summary.py --csv outputs/d24_tuning_session.csv --metric pnl --top-n 5
  
  # 거래 수 기준 상위 10개
  python scripts/show_tuning_summary.py --csv outputs/d24_tuning_session.csv --metric trades --top-n 10
        """
    )
    
    parser.add_argument(
        "--csv",
        required=True,
        help="CSV 파일 경로"
    )
    
    parser.add_argument(
        "--metric",
        default=None,
        help="정렬 기준 메트릭 이름 (선택사항)"
    )
    
    parser.add_argument(
        "--top-n",
        type=int,
        default=5,
        help="상위 N개 출력 (기본값: 5)"
    )
    
    args = parser.parse_args()
    
    try:
        # CSV 로드
        logger.info(f"Loading results from: {args.csv}")
        results = load_results_from_csv(args.csv)
        
        if not results:
            logger.error("No results loaded from CSV")
            return 1
        
        # 분석기 생성
        analyzer = TuningAnalyzer(results)
        
        # 요약 출력
        print("\n" + "="*70)
        print("[D26_TUNING] RESULT SUMMARY")
        print("="*70)
        
        summary = analyzer.summarize()
        print(f"Total Iterations:    {summary['total_iterations']}")
        print(f"Total Workers:       {summary['total_workers']}")
        print(f"Unique Sessions:     {summary['unique_sessions']}")
        print(f"Metrics:             {', '.join(summary['metrics_keys'])}")
        print(f"Parameters:          {', '.join(summary['param_keys'])}")
        print(f"Workers:             {', '.join(summary['workers'])}")
        print(f"Sessions:            {', '.join(summary['sessions'])}")
        
        # 메트릭 기준 랭킹 (선택사항)
        if args.metric:
            print(f"\n{'='*70}")
            print(f"[D26_TUNING] TOP {args.top_n} BY {args.metric.upper()}")
            print(f"{'='*70}")
            
            ranked = analyzer.rank_by_metric(args.metric, top_n=args.top_n, ascending=False)
            
            if ranked:
                for idx, result in enumerate(ranked, 1):
                    print(f"\n{idx}. {format_result_summary(result)}")
            else:
                print(f"No results found for metric: {args.metric}")
        
        print("\n" + "="*70 + "\n")
        
        return 0
    
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
