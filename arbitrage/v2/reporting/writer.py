"""
D205-1: Reporting Writer

목적:
- aggregator로부터 집계된 metrics를 v2_pnl_daily, v2_ops_daily에 upsert
- Idempotent: 동일 date에 대해 재실행 시 UPDATE
- PostgreSQL ON CONFLICT ... DO UPDATE 사용

Pattern: V2LedgerStorage (psycopg2 연결)

Author: arbitrage-lite V2
Date: 2025-12-30
"""

import logging
from typing import Dict, Any
from datetime import date
import psycopg2

logger = logging.getLogger(__name__)


def upsert_pnl_daily(
    connection_string: str,
    pnl_metrics: Dict[str, Any],
) -> None:
    """
    v2_pnl_daily 테이블에 upsert
    
    Args:
        connection_string: PostgreSQL 연결 문자열
        pnl_metrics: aggregate_pnl_daily() 반환값
        
    Logic:
        - INSERT ... ON CONFLICT (date) DO UPDATE
        - updated_at = NOW()
    """
    upsert_sql = """
    INSERT INTO v2_pnl_daily (
        date, gross_pnl, net_pnl, fees, volume,
        trades_count, wins, losses, winrate_pct,
        avg_spread, max_drawdown, sharpe_ratio
    ) VALUES (
        %s, %s, %s, %s, %s,
        %s, %s, %s, %s,
        %s, %s, %s
    )
    ON CONFLICT (date) DO UPDATE SET
        gross_pnl = EXCLUDED.gross_pnl,
        net_pnl = EXCLUDED.net_pnl,
        fees = EXCLUDED.fees,
        volume = EXCLUDED.volume,
        trades_count = EXCLUDED.trades_count,
        wins = EXCLUDED.wins,
        losses = EXCLUDED.losses,
        winrate_pct = EXCLUDED.winrate_pct,
        avg_spread = EXCLUDED.avg_spread,
        max_drawdown = EXCLUDED.max_drawdown,
        sharpe_ratio = EXCLUDED.sharpe_ratio,
        updated_at = NOW()
    """
    
    try:
        with psycopg2.connect(connection_string) as conn:
            with conn.cursor() as cur:
                cur.execute(upsert_sql, (
                    pnl_metrics["date"],
                    pnl_metrics["gross_pnl"],
                    pnl_metrics["net_pnl"],
                    pnl_metrics["fees"],
                    pnl_metrics["volume"],
                    pnl_metrics["trades_count"],
                    pnl_metrics["wins"],
                    pnl_metrics["losses"],
                    pnl_metrics["winrate_pct"],
                    pnl_metrics["avg_spread"],
                    pnl_metrics["max_drawdown"],
                    pnl_metrics["sharpe_ratio"],
                ))
            conn.commit()
            logger.info(f"Upserted PnL for {pnl_metrics['date']}: net_pnl={pnl_metrics['net_pnl']}, trades={pnl_metrics['trades_count']}")
    
    except Exception as e:
        logger.error(f"Failed to upsert PnL for {pnl_metrics['date']}: {e}")
        raise


def upsert_ops_daily(
    connection_string: str,
    ops_metrics: Dict[str, Any],
) -> None:
    """
    v2_ops_daily 테이블에 upsert
    
    Args:
        connection_string: PostgreSQL 연결 문자열
        ops_metrics: aggregate_ops_daily() 반환값
        
    Logic:
        - INSERT ... ON CONFLICT (date) DO UPDATE
        - updated_at = NOW()
    """
    upsert_sql = """
    INSERT INTO v2_ops_daily (
        date, orders_count, fills_count, rejects_count, fill_rate_pct,
        avg_slippage_bps, latency_p50_ms, latency_p95_ms,
        api_errors, rate_limit_hits, reconnects,
        avg_cpu_pct, avg_memory_mb
    ) VALUES (
        %s, %s, %s, %s, %s,
        %s, %s, %s,
        %s, %s, %s,
        %s, %s
    )
    ON CONFLICT (date) DO UPDATE SET
        orders_count = EXCLUDED.orders_count,
        fills_count = EXCLUDED.fills_count,
        rejects_count = EXCLUDED.rejects_count,
        fill_rate_pct = EXCLUDED.fill_rate_pct,
        avg_slippage_bps = EXCLUDED.avg_slippage_bps,
        latency_p50_ms = EXCLUDED.latency_p50_ms,
        latency_p95_ms = EXCLUDED.latency_p95_ms,
        api_errors = EXCLUDED.api_errors,
        rate_limit_hits = EXCLUDED.rate_limit_hits,
        reconnects = EXCLUDED.reconnects,
        avg_cpu_pct = EXCLUDED.avg_cpu_pct,
        avg_memory_mb = EXCLUDED.avg_memory_mb,
        updated_at = NOW()
    """
    
    try:
        with psycopg2.connect(connection_string) as conn:
            with conn.cursor() as cur:
                cur.execute(upsert_sql, (
                    ops_metrics["date"],
                    ops_metrics["orders_count"],
                    ops_metrics["fills_count"],
                    ops_metrics["rejects_count"],
                    ops_metrics["fill_rate_pct"],
                    ops_metrics["avg_slippage_bps"],
                    ops_metrics["latency_p50_ms"],
                    ops_metrics["latency_p95_ms"],
                    ops_metrics["api_errors"],
                    ops_metrics["rate_limit_hits"],
                    ops_metrics["reconnects"],
                    ops_metrics["avg_cpu_pct"],
                    ops_metrics["avg_memory_mb"],
                ))
            conn.commit()
            logger.info(f"Upserted Ops for {ops_metrics['date']}: orders={ops_metrics['orders_count']}, fills={ops_metrics['fills_count']}, fill_rate={ops_metrics['fill_rate_pct']}%")
    
    except Exception as e:
        logger.error(f"Failed to upsert Ops for {ops_metrics['date']}: {e}")
        raise
