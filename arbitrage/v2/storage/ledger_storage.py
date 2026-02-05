"""
D204-1: V2 Ledger Storage (PostgreSQL DAO Layer)

SSOT: db/schema/v2_schema.sql
Pattern: arbitrage/alerting/storage/postgres_storage.py (연결/쿼리 패턴)

목적:
- Paper/LIVE 실행 시 orders/fills/trades를 PostgreSQL에 기록
- v2_schema.sql 테이블에 대한 DAO 레이어 제공
- 최소 구현 (Hook point), 과도한 기능 금지

Author: arbitrage-lite V2
Date: 2025-12-30
"""

import logging
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Dict, Any, Optional

# D205-2 REOPEN-2: timestamp 유틸
from arbitrage.v2.utils.timestamp import to_utc_naive

logger = logging.getLogger(__name__)


def _normalize_to_utc_naive(dt: datetime) -> datetime:
    """
    Normalize datetime to UTC naive (SSOT for TIMESTAMP columns)
    
    **D204-2 Hotfix:** 명확한 UTC 변환 보장
    - tz-aware → UTC로 변환 후 tzinfo 제거
    - tz-naive → 이미 UTC naive로 간주 (caller 책임)
    
    Pattern: PostgreSQLAlertStorage._normalize_to_utc_naive()
    
    Args:
        dt: datetime (tz-aware or naive)
        
    Returns:
        UTC naive datetime (tzinfo removed)
        
    Examples:
        >>> from datetime import datetime, timezone, timedelta
        >>> # tz-aware (UTC+9)
        >>> dt_kst = datetime(2025, 12, 30, 12, 0, 0, tzinfo=timezone(timedelta(hours=9)))
        >>> _normalize_to_utc_naive(dt_kst)
        datetime(2025, 12, 30, 3, 0, 0)  # UTC naive
        
        >>> # tz-naive (already UTC)
        >>> dt_naive = datetime(2025, 12, 30, 3, 0, 0)
        >>> _normalize_to_utc_naive(dt_naive)
        datetime(2025, 12, 30, 3, 0, 0)  # unchanged
    """
    if dt.tzinfo is not None:
        # tz-aware → UTC로 변환 후 tzinfo 제거
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    else:
        # tz-naive → 이미 UTC naive로 간주
        # 주의: caller가 UTC naive임을 보장해야 함
        return dt


class V2LedgerStorage:
    """
    V2 Ledger Storage (PostgreSQL DAO)
    
    SSOT: db/schema/v2_schema.sql
    - v2_orders: 주문 기록
    - v2_fills: 체결 기록
    - v2_trades: 차익거래 기록
    
    Pattern: PostgreSQLAlertStorage (연결/쿼리)
    
    Usage:
        storage = V2LedgerStorage(connection_string="postgresql://...")
        storage.insert_order(run_id="d204_2_20251230_0300", ...)
        orders = storage.get_orders_by_run_id("d204_2_20251230_0300")
    """
    
    def __init__(self, connection_string: str, ensure_schema: bool = True):
        """
        Initialize V2 Ledger Storage
        
        Args:
            connection_string: PostgreSQL connection string
                Example: "postgresql://arbitrage:password@localhost:5432/arbitrage"
            ensure_schema: Whether to check schema existence (default: True)
        """
        self.connection_string = connection_string
        if ensure_schema:
            self._ensure_schema_exists()
    
    def _get_connection(self):
        """Get database connection (Pattern: PostgreSQLAlertStorage)"""
        return psycopg2.connect(self.connection_string)
    
    def _ensure_schema_exists(self):
        """
        Check if v2_schema.sql tables exist
        
        Note: 실제 테이블 생성은 db/schema/v2_schema.sql로 수동 실행
        이 메서드는 테이블 존재 여부만 확인 (마이그레이션 체크)
        """
        check_sql = """
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_name IN ('v2_orders', 'v2_fills', 'v2_trades')
        """
        
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(check_sql)
                    tables = [row[0] for row in cur.fetchall()]
                    
                    if 'v2_orders' not in tables:
                        logger.warning("v2_orders table not found. Run: psql -f db/schema/v2_schema.sql")
                    if 'v2_fills' not in tables:
                        logger.warning("v2_fills table not found. Run: psql -f db/schema/v2_schema.sql")
                    if 'v2_trades' not in tables:
                        logger.warning("v2_trades table not found. Run: psql -f db/schema/v2_schema.sql")
        except Exception as e:
            logger.warning(f"Schema check failed: {e}")
    
    def verify_schema(self, required_tables: List[str]) -> List[str]:
        """
        Verify required tables exist
        
        Args:
            required_tables: List of required table names
            
        Returns:
            List of missing table names (empty if all exist)
        """
        check_sql = """
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public'
        """
        
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(check_sql)
                    existing_tables = [row[0] for row in cur.fetchall()]
                    missing = [t for t in required_tables if t not in existing_tables]
                    return missing
        except Exception as e:
            logger.error(f"Schema verification failed: {e}")
            return required_tables
    
    # ========================================================================
    # Orders (v2_orders)
    # ========================================================================
    
    def insert_order(
        self,
        run_id: str,
        order_id: str,
        timestamp: datetime,
        exchange: str,
        symbol: str,
        side: str,
        order_type: str,
        quantity: Optional[float],
        price: Optional[float],
        status: str,
        route_id: Optional[str] = None,
        strategy_id: Optional[str] = None,
    ) -> None:
        """
        Insert order record into v2_orders
        
        Args:
            run_id: 실행 세션 ID (d204_2_YYYYMMDD_HHMM)
            order_id: 주문 ID (거래소 반환값)
            timestamp: 주문 생성 시각
            exchange: upbit, binance 등
            symbol: BTC/KRW, BTC/USDT 등
            side: BUY, SELL
            order_type: MARKET, LIMIT
            quantity: 주문 수량 (base asset)
            price: 주문 가격 (quote asset)
            status: pending, filled, canceled, failed
            route_id: 차익거래 route ID (optional)
            strategy_id: 전략 ID (optional)
        """
        timestamp_utc = _normalize_to_utc_naive(timestamp)
        
        insert_sql = """
        INSERT INTO v2_orders (
            run_id, order_id, timestamp, exchange, symbol, side, order_type,
            quantity, price, status, route_id, strategy_id
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(insert_sql, (
                        run_id, order_id, timestamp_utc, exchange, symbol,
                        side, order_type, quantity, price, status,
                        route_id, strategy_id
                    ))
                conn.commit()
                logger.debug(f"Inserted order: {order_id} ({exchange} {symbol} {side})")
        except Exception as e:
            logger.error(f"Failed to insert order {order_id}: {e}")
            raise
    
    def get_orders_by_run_id(self, run_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get orders by run_id
        
        Args:
            run_id: 실행 세션 ID
            limit: 최대 조회 건수 (default: 100)
            
        Returns:
            List of order records (dict)
        """
        select_sql = """
        SELECT * FROM v2_orders
        WHERE run_id = %s
        ORDER BY timestamp DESC
        LIMIT %s
        """
        
        try:
            with self._get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute(select_sql, (run_id, limit))
                    # D205-2 REOPEN-2: UTC naive 변환
                    orders = []
                    for row in cur.fetchall():
                        order = dict(row)
                        if 'timestamp' in order and order['timestamp']:
                            order['timestamp'] = to_utc_naive(order['timestamp'])
                        orders.append(order)
                    return orders
        except Exception as e:
            logger.error(f"Failed to get orders for run_id {run_id}: {e}")
            return []
    
    def get_order_by_id(self, order_id: str) -> Optional[Dict[str, Any]]:
        """
        Get single order by order_id
        
        Args:
            order_id: 주문 ID
            
        Returns:
            Order record (dict) or None
        """
        select_sql = """
        SELECT * FROM v2_orders
        WHERE order_id = %s
        LIMIT 1
        """
        
        try:
            with self._get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute(select_sql, (order_id,))
                    row = cur.fetchone()
                    if row:
                        order = dict(row)
                        # D205-2 REOPEN-2: UTC naive 변환
                        if 'timestamp' in order and order['timestamp']:
                            order['timestamp'] = to_utc_naive(order['timestamp'])
                        return order
                    return None
        except Exception as e:
            logger.error(f"Failed to get order {order_id}: {e}")
            return None
    
    def update_order_status(self, order_id: str, status: str) -> None:
        """
        Update order status
        
        Args:
            order_id: 주문 ID
            status: pending, filled, canceled, failed
        """
        update_sql = """
        UPDATE v2_orders
        SET status = %s, updated_at = NOW()
        WHERE order_id = %s
        """
        
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(update_sql, (status, order_id))
                conn.commit()
                logger.debug(f"Updated order {order_id} status to {status}")
        except Exception as e:
            logger.error(f"Failed to update order {order_id} status: {e}")
            raise
    
    # ========================================================================
    # Fills (v2_fills)
    # ========================================================================
    
    def insert_fill(
        self,
        run_id: str,
        order_id: str,
        fill_id: str,
        timestamp: datetime,
        exchange: str,
        symbol: str,
        side: str,
        filled_quantity: float,
        filled_price: float,
        fee: float,
        fee_currency: str,
    ) -> None:
        """
        Insert fill record into v2_fills
        
        Args:
            run_id: 실행 세션 ID
            order_id: 주문 ID (v2_orders.order_id 참조)
            fill_id: 체결 ID (거래소 반환값)
            timestamp: 체결 시각
            exchange: upbit, binance 등
            symbol: BTC/KRW, BTC/USDT 등
            side: BUY, SELL
            filled_quantity: 체결 수량
            filled_price: 체결 가격
            fee: 수수료
            fee_currency: 수수료 통화 (KRW, USDT, BTC 등)
        """
        timestamp_utc = _normalize_to_utc_naive(timestamp)
        
        insert_sql = """
        INSERT INTO v2_fills (
            run_id, order_id, fill_id, timestamp, exchange, symbol, side,
            filled_quantity, filled_price, fee, fee_currency
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(insert_sql, (
                        run_id, order_id, fill_id, timestamp_utc, exchange, symbol, side,
                        filled_quantity, filled_price, fee, fee_currency
                    ))
                conn.commit()
                logger.debug(f"Inserted fill: {fill_id} (order: {order_id}, qty: {filled_quantity})")
        except Exception as e:
            logger.error(f"Failed to insert fill {fill_id}: {e}")
            raise
    
    def get_fills_by_order_id(self, order_id: str) -> List[Dict[str, Any]]:
        """
        Get fills by order_id
        
        Args:
            order_id: 주문 ID
            
        Returns:
            List of fill records (dict)
        """
        select_sql = """
        SELECT * FROM v2_fills
        WHERE order_id = %s
        ORDER BY timestamp DESC
        """
        
        try:
            with self._get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute(select_sql, (order_id,))
                    return [dict(row) for row in cur.fetchall()]
        except Exception as e:
            logger.error(f"Failed to get fills for order {order_id}: {e}")
            return []
    
    def get_fills_by_run_id(self, run_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get fills by run_id
        
        Args:
            run_id: 실행 세션 ID
            limit: 최대 조회 건수 (default: 100)
            
        Returns:
            List of fill records (dict)
        """
        select_sql = """
        SELECT * FROM v2_fills
        WHERE run_id = %s
        ORDER BY timestamp DESC
        LIMIT %s
        """
        
        try:
            with self._get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute(select_sql, (run_id, limit))
                    return [dict(row) for row in cur.fetchall()]
        except Exception as e:
            logger.error(f"Failed to get fills for run_id {run_id}: {e}")
            return []
    
    # ========================================================================
    # Trades (v2_trades)
    # ========================================================================
    
    def insert_trade(
        self,
        run_id: str,
        trade_id: str,
        timestamp: datetime,
        entry_exchange: str,
        entry_symbol: str,
        entry_side: str,
        entry_order_id: str,
        entry_quantity: float,
        entry_price: float,
        entry_timestamp: datetime,
        status: str = "open",
        exit_exchange: Optional[str] = None,
        exit_symbol: Optional[str] = None,
        exit_side: Optional[str] = None,
        exit_order_id: Optional[str] = None,
        exit_quantity: Optional[float] = None,
        exit_price: Optional[float] = None,
        exit_timestamp: Optional[datetime] = None,
        realized_pnl: Optional[float] = None,
        unrealized_pnl: Optional[float] = None,
        total_fee: Optional[float] = None,
        route_id: Optional[str] = None,
        strategy_id: Optional[str] = None,
    ) -> None:
        """
        Insert trade record into v2_trades
        
        Args:
            run_id: 실행 세션 ID
            trade_id: 차익거래 ID (자체 생성, format: trade_{run_id}_{seq})
            timestamp: 거래 시작 시각
            entry_exchange: 진입 거래소
            entry_symbol: 진입 심볼
            entry_side: BUY or SELL
            entry_order_id: 진입 주문 ID
            entry_quantity: 진입 수량
            entry_price: 진입 평균 가격
            entry_timestamp: 진입 체결 시각
            status: open, closed, failed (default: open)
            exit_exchange: 청산 거래소 (optional)
            exit_symbol: 청산 심볼 (optional)
            exit_side: BUY or SELL (optional)
            exit_order_id: 청산 주문 ID (optional)
            exit_quantity: 청산 수량 (optional)
            exit_price: 청산 평균 가격 (optional)
            exit_timestamp: 청산 체결 시각 (optional)
            realized_pnl: 실현 손익 (optional)
            unrealized_pnl: 미실현 손익 (optional)
            total_fee: 총 수수료 (optional)
            route_id: 차익거래 route (optional)
            strategy_id: 전략 ID (optional)
        """
        timestamp_utc = _normalize_to_utc_naive(timestamp)
        entry_timestamp_utc = _normalize_to_utc_naive(entry_timestamp)
        exit_timestamp_utc = _normalize_to_utc_naive(exit_timestamp) if exit_timestamp else None
        
        insert_sql = """
        INSERT INTO v2_trades (
            run_id, trade_id, timestamp,
            entry_exchange, entry_symbol, entry_side, entry_order_id,
            entry_quantity, entry_price, entry_timestamp,
            exit_exchange, exit_symbol, exit_side, exit_order_id,
            exit_quantity, exit_price, exit_timestamp,
            realized_pnl, unrealized_pnl, total_fee,
            status, route_id, strategy_id
        ) VALUES (
            %s, %s, %s,
            %s, %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s, %s, %s,
            %s, %s, %s,
            %s, %s, %s
        )
        """
        
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(insert_sql, (
                        run_id, trade_id, timestamp_utc,
                        entry_exchange, entry_symbol, entry_side, entry_order_id,
                        entry_quantity, entry_price, entry_timestamp_utc,
                        exit_exchange, exit_symbol, exit_side, exit_order_id,
                        exit_quantity, exit_price, exit_timestamp_utc,
                        realized_pnl, unrealized_pnl, total_fee,
                        status, route_id, strategy_id
                    ))
                conn.commit()
                logger.debug(f"Inserted trade: {trade_id} ({status})")
        except Exception as e:
            logger.error(f"Failed to insert trade {trade_id}: {e}")
            raise
    
    def get_trades_by_run_id(self, run_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get trades by run_id
        
        Args:
            run_id: 실행 세션 ID
            limit: 최대 조회 건수 (default: 100)
            
        Returns:
            List of trade records (dict)
        """
        select_sql = """
        SELECT * FROM v2_trades
        WHERE run_id = %s
        ORDER BY timestamp DESC
        LIMIT %s
        """
        
        try:
            with self._get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute(select_sql, (run_id, limit))
                    return [dict(row) for row in cur.fetchall()]
        except Exception as e:
            logger.error(f"Failed to get trades for run_id {run_id}: {e}")
            return []
    
    def get_trade_by_id(self, trade_id: str) -> Optional[Dict[str, Any]]:
        """
        Get single trade by trade_id
        
        Args:
            trade_id: 차익거래 ID
            
        Returns:
            Trade record (dict) or None
        """
        select_sql = """
        SELECT * FROM v2_trades
        WHERE trade_id = %s
        LIMIT 1
        """
        
        try:
            with self._get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute(select_sql, (trade_id,))
                    row = cur.fetchone()
                    return dict(row) if row else None
        except Exception as e:
            logger.error(f"Failed to get trade {trade_id}: {e}")
            return None
    
    def update_trade_exit(
        self,
        trade_id: str,
        exit_exchange: str,
        exit_symbol: str,
        exit_side: str,
        exit_order_id: str,
        exit_quantity: float,
        exit_price: float,
        exit_timestamp: datetime,
        realized_pnl: float,
        total_fee: float,
        status: str = "closed",
    ) -> None:
        """
        Update trade with exit (close) information
        
        Args:
            trade_id: 차익거래 ID
            exit_exchange: 청산 거래소
            exit_symbol: 청산 심볼
            exit_side: BUY or SELL
            exit_order_id: 청산 주문 ID
            exit_quantity: 청산 수량
            exit_price: 청산 평균 가격
            exit_timestamp: 청산 체결 시각
            realized_pnl: 실현 손익
            total_fee: 총 수수료
            status: closed, failed (default: closed)
        """
        exit_timestamp_utc = _normalize_to_utc_naive(exit_timestamp)
        
        update_sql = """
        UPDATE v2_trades
        SET exit_exchange = %s, exit_symbol = %s, exit_side = %s, exit_order_id = %s,
            exit_quantity = %s, exit_price = %s, exit_timestamp = %s,
            realized_pnl = %s, total_fee = %s, status = %s, updated_at = NOW()
        WHERE trade_id = %s
        """
        
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(update_sql, (
                        exit_exchange, exit_symbol, exit_side, exit_order_id,
                        exit_quantity, exit_price, exit_timestamp_utc,
                        realized_pnl, total_fee, status,
                        trade_id
                    ))
                conn.commit()
                logger.debug(f"Updated trade {trade_id} with exit (status: {status})")
        except Exception as e:
            logger.error(f"Failed to update trade {trade_id} exit: {e}")
            raise
