#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CSV → PostgreSQL Migration Script (PHASE D – MODULE D1)
========================================================

CSV 로그 파일을 PostgreSQL 데이터베이스로 마이그레이션합니다.

사용법:
    python scripts/migrate_csv_to_postgres.py --config config/base.yml
    python scripts/migrate_csv_to_postgres.py --config config/base.yml --dry-run
    python scripts/migrate_csv_to_postgres.py --config config/base.yml --limit 100

옵션:
    --config: 설정 파일 경로 (기본값: config/base.yml)
    --dry-run: 실제 INSERT 대신 요약만 출력
    --limit: 테스트용 행 수 제한 (기본값: 무제한)

특징:
    - Idempotent: 같은 CSV를 여러 번 마이그레이션해도 중복 데이터 없음
    - 트랜잭션 기반: 안정성 보장
    - 상세 로그: 마이그레이션 진행 상황 추적
"""

import sys
import csv
import logging
import argparse
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, List, Optional

# 프로젝트 루트 추가
sys.path.insert(0, str(Path(__file__).parent.parent))

from arbitrage.models import Position, OrderLeg, SpreadOpportunity
from arbitrage.storage import PostgresStorage

# 설정 로드 함수 (간단한 YAML 파서)
def load_config(config_path: str) -> Dict:
    """YAML 설정 파일 로드"""
    import yaml
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)


class CsvToPostgresMigrator:
    """CSV → PostgreSQL 마이그레이션 도구"""

    def __init__(self, config: Dict, dry_run: bool = False, limit: Optional[int] = None):
        """
        Args:
            config: 설정 딕셔너리
            dry_run: True면 실제 INSERT 대신 요약만 출력
            limit: 테스트용 행 수 제한
        """
        self.config = config
        self.dry_run = dry_run
        self.limit = limit
        self.data_dir = Path(config.get("data_dir", "data"))
        
        # PostgreSQL 연결
        try:
            postgres_cfg = config.get("storage", {}).get("postgres", {})
            self.storage = PostgresStorage(postgres_cfg)
            logger.info("[Migrator] PostgreSQL connection established")
        except Exception as e:
            logger.error(f"[Migrator] Failed to connect to PostgreSQL: {e}")
            raise

    def migrate_positions(self) -> Dict:
        """positions.csv 마이그레이션"""
        logger.info("[Migrator] Starting positions migration...")
        
        positions_file = self.data_dir / "positions.csv"
        if not positions_file.exists():
            logger.warning(f"[Migrator] positions.csv not found at {positions_file}")
            return {"skipped": 0, "inserted": 0, "updated": 0, "errors": 0}
        
        stats = {"skipped": 0, "inserted": 0, "updated": 0, "errors": 0}
        
        try:
            with positions_file.open("r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for i, row in enumerate(reader):
                    if self.limit and i >= self.limit:
                        break
                    
                    try:
                        # CSV 행 → Position 객체
                        ts_open = datetime.fromisoformat(row["timestamp_open"])
                        if ts_open.tzinfo is None:
                            ts_open = ts_open.replace(tzinfo=timezone.utc)
                        
                        pos = Position(
                            symbol=row["symbol"],
                            direction=row["direction"],
                            size=float(row["size"]),
                            entry_upbit_price=float(row["entry_upbit_price"]),
                            entry_binance_price=float(row["entry_binance_price"]),
                            entry_spread_pct=float(row["entry_spread_pct"]),
                            timestamp_open=ts_open,
                            status=row.get("status", "OPEN"),
                        )
                        
                        if row.get("timestamp_close"):
                            ts_close = datetime.fromisoformat(row["timestamp_close"])
                            if ts_close.tzinfo is None:
                                ts_close = ts_close.replace(tzinfo=timezone.utc)
                            pos.timestamp_close = ts_close
                        
                        if row.get("exit_upbit_price"):
                            pos.exit_upbit_price = float(row["exit_upbit_price"])
                        if row.get("exit_binance_price"):
                            pos.exit_binance_price = float(row["exit_binance_price"])
                        if row.get("exit_spread_pct"):
                            pos.exit_spread_pct = float(row["exit_spread_pct"])
                        if row.get("pnl_krw"):
                            pos.pnl_krw = float(row["pnl_krw"])
                        if row.get("pnl_pct"):
                            pos.pnl_pct = float(row["pnl_pct"])
                        
                        # DB에 저장
                        if not self.dry_run:
                            if pos.status == "OPEN":
                                self.storage.log_position_open(pos)
                                stats["inserted"] += 1
                            else:
                                self.storage.log_position_close(pos)
                                stats["updated"] += 1
                        else:
                            stats["inserted"] += 1
                    
                    except Exception as e:
                        logger.error(f"[Migrator] Error processing position row {i}: {e}")
                        stats["errors"] += 1
        
        except Exception as e:
            logger.error(f"[Migrator] Error reading positions.csv: {e}")
            stats["errors"] += 1
        
        logger.info(
            f"[Migrator] Positions migration complete: "
            f"inserted={stats['inserted']}, updated={stats['updated']}, errors={stats['errors']}"
        )
        return stats

    def migrate_orders(self) -> Dict:
        """orders.csv 마이그레이션"""
        logger.info("[Migrator] Starting orders migration...")
        
        orders_file = self.data_dir / "orders.csv"
        if not orders_file.exists():
            logger.warning(f"[Migrator] orders.csv not found at {orders_file}")
            return {"skipped": 0, "inserted": 0, "errors": 0}
        
        stats = {"skipped": 0, "inserted": 0, "errors": 0}
        
        try:
            with orders_file.open("r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for i, row in enumerate(reader):
                    if self.limit and i >= self.limit:
                        break
                    
                    try:
                        # CSV 행 → OrderLeg 객체
                        timestamp = datetime.fromisoformat(row["timestamp"])
                        if timestamp.tzinfo is None:
                            timestamp = timestamp.replace(tzinfo=timezone.utc)
                        
                        leg = OrderLeg(
                            symbol=row["symbol"],
                            venue=row["venue"],
                            side=row["side"],
                            qty=float(row["qty"]),
                            price_theoretical=float(row["price_theoretical"]),
                            timestamp=timestamp,
                            leg_id=row["leg_id"],
                        )
                        
                        if row.get("price_effective"):
                            leg.price_effective = float(row["price_effective"])
                        if row.get("slippage_bps"):
                            leg.slippage_bps = float(row["slippage_bps"])
                        if row.get("order_id"):
                            leg.order_id = row["order_id"]
                        
                        # DB에 저장
                        if not self.dry_run:
                            self.storage.log_order(leg)
                        
                        stats["inserted"] += 1
                    
                    except Exception as e:
                        logger.error(f"[Migrator] Error processing order row {i}: {e}")
                        stats["errors"] += 1
        
        except Exception as e:
            logger.error(f"[Migrator] Error reading orders.csv: {e}")
            stats["errors"] += 1
        
        logger.info(
            f"[Migrator] Orders migration complete: "
            f"inserted={stats['inserted']}, errors={stats['errors']}"
        )
        return stats

    def migrate_spreads(self) -> Dict:
        """spreads.csv 마이그레이션"""
        logger.info("[Migrator] Starting spreads migration...")
        
        spreads_file = self.data_dir / "spreads.csv"
        if not spreads_file.exists():
            logger.warning(f"[Migrator] spreads.csv not found at {spreads_file}")
            return {"skipped": 0, "inserted": 0, "errors": 0}
        
        stats = {"skipped": 0, "inserted": 0, "errors": 0}
        
        try:
            with spreads_file.open("r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for i, row in enumerate(reader):
                    if self.limit and i >= self.limit:
                        break
                    
                    try:
                        # CSV 행 → SpreadOpportunity 객체
                        timestamp_ms = int(datetime.fromisoformat(row["timestamp"]).timestamp() * 1000)
                        
                        opp = SpreadOpportunity(
                            symbol=row["symbol"],
                            upbit_price=float(row["upbit_price"]),
                            binance_price=float(row["binance_price"]),
                            binance_price_krw=float(row["binance_price_krw"]),
                            spread_pct=float(row["spread_pct"]),
                            net_spread_pct=float(row["net_spread_pct"]),
                            timestamp=timestamp_ms,
                            is_opportunity=row.get("is_opportunity", "False").lower() == "true",
                        )
                        
                        # DB에 저장
                        if not self.dry_run:
                            self.storage.log_spread(opp)
                        
                        stats["inserted"] += 1
                    
                    except Exception as e:
                        logger.error(f"[Migrator] Error processing spread row {i}: {e}")
                        stats["errors"] += 1
        
        except Exception as e:
            logger.error(f"[Migrator] Error reading spreads.csv: {e}")
            stats["errors"] += 1
        
        logger.info(
            f"[Migrator] Spreads migration complete: "
            f"inserted={stats['inserted']}, errors={stats['errors']}"
        )
        return stats

    def run(self) -> None:
        """전체 마이그레이션 실행"""
        logger.info("=" * 70)
        logger.info("CSV → PostgreSQL Migration Started")
        logger.info("=" * 70)
        
        if self.dry_run:
            logger.warning("[Migrator] DRY-RUN MODE: No actual data will be inserted")
        
        if self.limit:
            logger.warning(f"[Migrator] LIMIT MODE: Processing only {self.limit} rows per table")
        
        # 마이그레이션 실행
        positions_stats = self.migrate_positions()
        orders_stats = self.migrate_orders()
        spreads_stats = self.migrate_spreads()
        
        # 요약 출력
        logger.info("=" * 70)
        logger.info("Migration Summary")
        logger.info("=" * 70)
        logger.info(f"Positions: inserted={positions_stats['inserted']}, updated={positions_stats.get('updated', 0)}, errors={positions_stats['errors']}")
        logger.info(f"Orders:    inserted={orders_stats['inserted']}, errors={orders_stats['errors']}")
        logger.info(f"Spreads:   inserted={spreads_stats['inserted']}, errors={spreads_stats['errors']}")
        
        total_inserted = (
            positions_stats['inserted'] + 
            orders_stats['inserted'] + 
            spreads_stats['inserted']
        )
        total_errors = (
            positions_stats['errors'] + 
            orders_stats['errors'] + 
            spreads_stats['errors']
        )
        
        logger.info(f"Total: {total_inserted} rows inserted, {total_errors} errors")
        logger.info("=" * 70)


def main():
    """메인 함수"""
    parser = argparse.ArgumentParser(
        description="CSV → PostgreSQL Migration Tool (PHASE D – MODULE D1)"
    )
    parser.add_argument(
        "--config",
        default="config/base.yml",
        help="설정 파일 경로 (기본값: config/base.yml)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="실제 INSERT 대신 요약만 출력"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="테스트용 행 수 제한"
    )
    
    args = parser.parse_args()
    
    # 설정 로드
    try:
        config = load_config(args.config)
    except Exception as e:
        logger.error(f"Failed to load config: {e}")
        sys.exit(1)
    
    # 마이그레이션 실행
    try:
        migrator = CsvToPostgresMigrator(config, dry_run=args.dry_run, limit=args.limit)
        migrator.run()
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
