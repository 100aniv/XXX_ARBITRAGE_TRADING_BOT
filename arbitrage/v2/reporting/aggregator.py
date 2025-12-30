"""
D205-1: Reporting Aggregator

목적:
- v2_orders/fills/trades 테이블로부터 daily PnL 및 Ops metrics 집계
- CTE 기반 SQL 쿼리로 효율적 집계
- 집계 결과를 dict로 반환 (writer에서 DB insert)

Pattern: PostgreSQLAlertStorage (psycopg2 연결)

Author: arbitrage-lite V2
Date: 2025-12-30
"""

import logging
from typing import Dict, Any, Optional
from datetime import date, datetime, timezone
import psycopg2
from psycopg2.extras import RealDictCursor

logger = logging.getLogger(__name__)


def aggregate_pnl_daily(
    connection_string: str,
    target_date: date,
    run_id_prefix: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Daily PnL 집계
    
    Args:
        connection_string: PostgreSQL 연결 문자열
        target_date: 집계 대상 일자 (YYYY-MM-DD)
        run_id_prefix: run_id 필터 (optional, 예: "d204_2_")
        
    Returns:
        Dict with PnL metrics:
        {
            "date": date,
            "gross_pnl": float,
            "net_pnl": float,
            "fees": float,
            "volume": float,
            "trades_count": int,
            "wins": int,
            "losses": int,
            "winrate_pct": float,
            "avg_spread": float,
            "max_drawdown": float,
            "sharpe_ratio": float (or None),
        }
    
    Logic:
        - v2_trades에서 realized_pnl, total_fee 집계
        - v2_fills에서 volume (filled_quantity * filled_price) 집계
        - gross_pnl = SUM(realized_pnl), net_pnl = gross_pnl - fees
        - winrate = wins / total trades
    """
    query = """
    WITH daily_trades AS (
        SELECT
            DATE(timestamp) AS trade_date,
            COUNT(*) AS trades_count,
            SUM(CASE WHEN realized_pnl > 0 THEN 1 ELSE 0 END) AS wins,
            SUM(CASE WHEN realized_pnl <= 0 THEN 1 ELSE 0 END) AS losses,
            SUM(COALESCE(realized_pnl, 0)) AS gross_pnl,
            SUM(COALESCE(total_fee, 0)) AS fees
        FROM v2_trades
        WHERE DATE(timestamp) = %s
            AND status = 'closed'
            AND (%s IS NULL OR run_id LIKE %s)
        GROUP BY DATE(timestamp)
    ),
    daily_fills AS (
        SELECT
            DATE(timestamp) AS fill_date,
            SUM(filled_quantity * filled_price) AS volume
        FROM v2_fills
        WHERE DATE(timestamp) = %s
            AND (%s IS NULL OR run_id LIKE %s)
        GROUP BY DATE(timestamp)
    )
    SELECT
        t.trade_date AS date,
        COALESCE(t.trades_count, 0) AS trades_count,
        COALESCE(t.wins, 0) AS wins,
        COALESCE(t.losses, 0) AS losses,
        COALESCE(t.gross_pnl, 0) AS gross_pnl,
        COALESCE(t.fees, 0) AS fees,
        COALESCE(t.gross_pnl, 0) - COALESCE(t.fees, 0) AS net_pnl,
        CASE 
            WHEN t.trades_count > 0 THEN ROUND((t.wins::NUMERIC / t.trades_count * 100), 2)
            ELSE 0
        END AS winrate_pct,
        COALESCE(f.volume, 0) AS volume
    FROM daily_trades t
    LEFT JOIN daily_fills f ON t.trade_date = f.fill_date
    """
    
    run_id_like = f"{run_id_prefix}%" if run_id_prefix else None
    
    try:
        with psycopg2.connect(connection_string) as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query, (
                    target_date, run_id_like, run_id_like,
                    target_date, run_id_like, run_id_like,
                ))
                row = cur.fetchone()
                
                if not row:
                    logger.warning(f"No PnL data for {target_date}")
                    return {
                        "date": target_date,
                        "gross_pnl": 0.0,
                        "net_pnl": 0.0,
                        "fees": 0.0,
                        "volume": 0.0,
                        "trades_count": 0,
                        "wins": 0,
                        "losses": 0,
                        "winrate_pct": 0.0,
                        "avg_spread": None,
                        "max_drawdown": None,
                        "sharpe_ratio": None,
                    }
                
                return {
                    "date": row["date"],
                    "gross_pnl": float(row["gross_pnl"]),
                    "net_pnl": float(row["net_pnl"]),
                    "fees": float(row["fees"]),
                    "volume": float(row["volume"]),
                    "trades_count": int(row["trades_count"]),
                    "wins": int(row["wins"]),
                    "losses": int(row["losses"]),
                    "winrate_pct": float(row["winrate_pct"]),
                    "avg_spread": None,  # TODO: 향후 구현 (v2_trades에 spread 컬럼 추가 필요)
                    "max_drawdown": None,  # TODO: 향후 구현 (rolling PnL 필요)
                    "sharpe_ratio": None,  # TODO: 향후 구현 (volatility 필요)
                }
    
    except Exception as e:
        logger.error(f"Failed to aggregate PnL for {target_date}: {e}")
        raise


def aggregate_ops_daily(
    connection_string: str,
    target_date: date,
    run_id_prefix: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Daily Operational metrics 집계
    
    Args:
        connection_string: PostgreSQL 연결 문자열
        target_date: 집계 대상 일자 (YYYY-MM-DD)
        run_id_prefix: run_id 필터 (optional)
        
    Returns:
        Dict with Ops metrics:
        {
            "date": date,
            "orders_count": int,
            "fills_count": int,
            "rejects_count": int,
            "fill_rate_pct": float,
            "avg_slippage_bps": float (or None),
            "latency_p50_ms": float (or None),
            "latency_p95_ms": float (or None),
            "api_errors": int,
            "rate_limit_hits": int,
            "reconnects": int,
            "avg_cpu_pct": float (or None),
            "avg_memory_mb": float (or None),
        }
    
    Logic:
        - v2_orders에서 orders_count, rejects (status='failed')
        - v2_fills에서 fills_count
        - fill_rate = fills / orders
        - latency/slippage는 향후 v2_orders/fills에 컬럼 추가 필요
    """
    query = """
    WITH daily_orders AS (
        SELECT
            DATE(timestamp) AS order_date,
            COUNT(*) AS orders_count,
            SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) AS rejects_count
        FROM v2_orders
        WHERE DATE(timestamp) = %s
            AND (%s IS NULL OR run_id LIKE %s)
        GROUP BY DATE(timestamp)
    ),
    daily_fills AS (
        SELECT
            DATE(timestamp) AS fill_date,
            COUNT(*) AS fills_count
        FROM v2_fills
        WHERE DATE(timestamp) = %s
            AND (%s IS NULL OR run_id LIKE %s)
        GROUP BY DATE(timestamp)
    )
    SELECT
        o.order_date AS date,
        COALESCE(o.orders_count, 0) AS orders_count,
        COALESCE(f.fills_count, 0) AS fills_count,
        COALESCE(o.rejects_count, 0) AS rejects_count,
        CASE 
            WHEN o.orders_count > 0 THEN ROUND((f.fills_count::NUMERIC / o.orders_count * 100), 2)
            ELSE 0
        END AS fill_rate_pct
    FROM daily_orders o
    LEFT JOIN daily_fills f ON o.order_date = f.fill_date
    """
    
    run_id_like = f"{run_id_prefix}%" if run_id_prefix else None
    
    try:
        with psycopg2.connect(connection_string) as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query, (
                    target_date, run_id_like, run_id_like,
                    target_date, run_id_like, run_id_like,
                ))
                row = cur.fetchone()
                
                if not row:
                    logger.warning(f"No Ops data for {target_date}")
                    return {
                        "date": target_date,
                        "orders_count": 0,
                        "fills_count": 0,
                        "rejects_count": 0,
                        "fill_rate_pct": 0.0,
                        "avg_slippage_bps": None,
                        "latency_p50_ms": None,
                        "latency_p95_ms": None,
                        "api_errors": 0,
                        "rate_limit_hits": 0,
                        "reconnects": 0,
                        "avg_cpu_pct": None,
                        "avg_memory_mb": None,
                    }
                
                return {
                    "date": row["date"],
                    "orders_count": int(row["orders_count"]),
                    "fills_count": int(row["fills_count"]),
                    "rejects_count": int(row["rejects_count"]),
                    "fill_rate_pct": float(row["fill_rate_pct"]),
                    "avg_slippage_bps": None,  # TODO: v2_fills에 slippage 컬럼 추가 필요
                    "latency_p50_ms": None,  # TODO: v2_orders에 latency 컬럼 추가 필요
                    "latency_p95_ms": None,  # TODO: v2_orders에 latency 컬럼 추가 필요
                    "api_errors": 0,  # TODO: v2_orders에 error_code 컬럼 추가 필요
                    "rate_limit_hits": 0,  # TODO: 별도 로깅 필요
                    "reconnects": 0,  # TODO: WebSocket 로깅 필요
                    "avg_cpu_pct": None,  # TODO: 시스템 메트릭 수집 필요
                    "avg_memory_mb": None,  # TODO: 시스템 메트릭 수집 필요
                }
    
    except Exception as e:
        logger.error(f"Failed to aggregate Ops for {target_date}: {e}")
        raise
