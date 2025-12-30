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
    
    Returns:
        Dict with ops metrics
        
    Note (D205-2):
        - api_errors, rate_limit_hits, reconnects는 현재 Paper runner에서 추적 안 함 (기본값 0)
        - LIVE 모드 전환 시 실제 값 집계 예정 (v2_orders/v2_fills 테이블에 컬럼 추가 필요)
    """
    query = """
        WITH orders_agg AS (
            SELECT 
                DATE(timestamp) AS date,
                COUNT(*) AS orders_count,
                COUNT(CASE WHEN status = 'rejected' THEN 1 END) AS rejects_count
            FROM v2_orders
            WHERE DATE(timestamp) = %s
              AND (%s IS NULL OR run_id LIKE %s)
            GROUP BY DATE(timestamp)
        ),
        fills_agg AS (
            SELECT 
                DATE(timestamp) AS date,
                COUNT(*) AS fills_count
            FROM v2_fills
            WHERE DATE(timestamp) = %s
              AND (%s IS NULL OR run_id LIKE %s)
            GROUP BY DATE(timestamp)
        )
        SELECT 
            COALESCE(o.date, f.date) AS date,
            COALESCE(o.orders_count, 0) AS orders_count,
            COALESCE(o.rejects_count, 0) AS rejects_count,
            COALESCE(f.fills_count, 0) AS fills_count,
            CASE 
                WHEN COALESCE(o.orders_count, 0) > 0 
                THEN ROUND((COALESCE(f.fills_count, 0)::NUMERIC / o.orders_count) * 100, 2)
                ELSE 0.0
            END AS fill_rate_pct
        FROM orders_agg o
        FULL OUTER JOIN fills_agg f ON o.date = f.date
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
                    logger.warning(f"No ops data for {target_date}")
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
                
                # D205-2: 운영급 확장 계획
                # - api_errors: 현재 Paper에서 0, LIVE 전환 시 실제 API error log 집계
                # - rate_limit_hits: 현재 Paper에서 0, LIVE 전환 시 429 error 집계
                # - reconnects: 현재 Paper에서 0, LIVE 전환 시 WS reconnect 이벤트 집계
                # 구현 방향: v2_orders/v2_fills 테이블에 error_type 컬럼 추가, CTE 쿼리 확장
                
                return {
                    "date": row["date"],
                    "orders_count": int(row["orders_count"]),
                    "fills_count": int(row["fills_count"]),
                    "rejects_count": int(row["rejects_count"]),
                    "fill_rate_pct": float(row["fill_rate_pct"]),
                    "avg_slippage_bps": None,  # TODO D205-3: v2_fills.slippage_bps 컬럼 추가
                    "latency_p50_ms": None,  # TODO D205-3: v2_orders.latency_ms 컬럼 추가
                    "latency_p95_ms": None,  # TODO D205-3: v2_orders.latency_ms 컬럼 추가
                    "api_errors": 0,  # D205-2: Paper=0, LIVE 전환 시 error_type='api_error' COUNT
                    "rate_limit_hits": 0,  # D205-2: Paper=0, LIVE 전환 시 error_type='rate_limit' COUNT
                    "reconnects": 0,  # D205-2: Paper=0, LIVE 전환 시 reconnect 이벤트 테이블 필요
                    "avg_cpu_pct": None,  # TODO D205-3: 시스템 메트릭 테이블 추가
                    "avg_memory_mb": None,  # TODO D205-3: 시스템 메트릭 테이블 추가
                }
    
    except Exception as e:
        logger.error(f"Failed to aggregate ops for {target_date}: {e}")
        raise
