"""
D205-1: Daily Report CLI

목적:
- Daily PnL + Ops metrics 자동 집계 및 DB 저장
- 단일 명령으로 실행 가능한 CLI 엔트리포인트

Usage:
    python -m arbitrage.v2.reporting.run_daily_report --date 2025-12-30

Author: arbitrage-lite V2
Date: 2025-12-30
"""

import argparse
import logging
import sys
import os
from datetime import date, datetime, timedelta
from pathlib import Path
import json

# 프로젝트 루트를 sys.path에 추가
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from arbitrage.v2.reporting.aggregator import aggregate_pnl_daily, aggregate_ops_daily
from arbitrage.v2.reporting.writer import upsert_pnl_daily, upsert_ops_daily

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def main():
    """CLI 엔트리포인트"""
    parser = argparse.ArgumentParser(description="D205-1: Daily Report Generator")
    parser.add_argument(
        "--date",
        type=str,
        help="Target date (YYYY-MM-DD). Default: today",
    )
    parser.add_argument(
        "--db-connection-string",
        default="",
        help="PostgreSQL connection string",
    )
    parser.add_argument(
        "--run-id-prefix",
        default=None,
        help="Filter by run_id prefix (e.g., 'd204_2_')",
    )
    parser.add_argument(
        "--output-dir",
        default="logs/evidence",
        help="Output directory for report JSON",
    )
    
    args = parser.parse_args()
    
    # DB 연결 문자열 설정
    if args.db_connection_string:
        connection_string = args.db_connection_string
    else:
        # 환경변수 또는 기본값
        connection_string = os.getenv(
            "DATABASE_URL",
            "postgresql://arbitrage:arbitrage@localhost:5432/arbitrage"
        )
    
    # 타겟 날짜 파싱
    if args.date:
        try:
            target_date = datetime.strptime(args.date, "%Y-%m-%d").date()
        except ValueError:
            logger.error(f"Invalid date format: {args.date}. Use YYYY-MM-DD")
            sys.exit(1)
    else:
        target_date = date.today()
    
    logger.info("=" * 60)
    logger.info("D205-1: Daily Report Generator")
    logger.info("=" * 60)
    logger.info(f"Target date: {target_date}")
    logger.info(f"Run ID prefix: {args.run_id_prefix or 'All'}")
    logger.info(f"DB: {connection_string}")
    
    try:
        # 1. PnL 집계
        logger.info(f"[1/4] Aggregating PnL for {target_date}...")
        pnl_metrics = aggregate_pnl_daily(
            connection_string=connection_string,
            target_date=target_date,
            run_id_prefix=args.run_id_prefix,
        )
        logger.info(f"  → net_pnl: {pnl_metrics['net_pnl']}, trades: {pnl_metrics['trades_count']}, winrate: {pnl_metrics['winrate_pct']}%")
        
        # 2. PnL DB 저장
        logger.info(f"[2/4] Writing PnL to v2_pnl_daily...")
        upsert_pnl_daily(
            connection_string=connection_string,
            pnl_metrics=pnl_metrics,
        )
        
        # 3. Ops 집계
        logger.info(f"[3/4] Aggregating Ops for {target_date}...")
        ops_metrics = aggregate_ops_daily(
            connection_string=connection_string,
            target_date=target_date,
            run_id_prefix=args.run_id_prefix,
        )
        logger.info(f"  → orders: {ops_metrics['orders_count']}, fills: {ops_metrics['fills_count']}, fill_rate: {ops_metrics['fill_rate_pct']}%")
        
        # 4. Ops DB 저장
        logger.info(f"[4/4] Writing Ops to v2_ops_daily...")
        upsert_ops_daily(
            connection_string=connection_string,
            ops_metrics=ops_metrics,
        )
        
        # 5. 증거 JSON 저장
        output_dir = Path(args.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        report_data = {
            "date": str(target_date),
            "run_id_prefix": args.run_id_prefix,
            "pnl": pnl_metrics,
            "ops": ops_metrics,
            "generated_at": datetime.now().isoformat(),
        }
        
        # date를 문자열로 변환 (JSON serialization)
        report_data["pnl"]["date"] = str(report_data["pnl"]["date"])
        report_data["ops"]["date"] = str(report_data["ops"]["date"])
        
        report_file = output_dir / f"daily_report_{target_date}.json"
        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(report_data, f, indent=2, ensure_ascii=False)
        
        logger.info("=" * 60)
        logger.info("✅ SUCCESS")
        logger.info(f"Report saved: {report_file}")
        logger.info("=" * 60)
        
        sys.exit(0)
    
    except Exception as e:
        logger.error("=" * 60)
        logger.error(f"❌ FAILED: {e}")
        logger.error("=" * 60)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
