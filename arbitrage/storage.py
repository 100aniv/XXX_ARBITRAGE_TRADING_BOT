#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Storage Module
==============
저장 계층 추상화 (CSV/DB 기반)

책임:
- 포지션 기록 저장/로드
- 스프레드 기회 로그 저장
- 거래 내역 저장
- OrderLeg 기록 저장

구조:
- BaseStorage: 저장소 인터페이스 (추상 클래스)
- CsvStorage: CSV 파일 기반 구현 (현재 기본)
- PostgresStorage: PostgreSQL/TimescaleDB 기반 (PHASE D)
- RedisCacheStorage: Redis 캐시 헬퍼 (PHASE D)
"""

import json
import csv
import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime, timezone
from .models import Position, SpreadOpportunity, OrderLeg

logger = logging.getLogger(__name__)


class BaseStorage(ABC):
    """저장소 인터페이스 (추상 클래스)
    
    모든 저장소 구현은 이 인터페이스를 따릅니다.
    CSV, PostgreSQL, Redis 등 다양한 백엔드로 확장 가능합니다.
    """

    @abstractmethod
    def log_spread(self, opportunity: SpreadOpportunity) -> None:
        """스프레드 기회 기록"""
        pass

    @abstractmethod
    def log_position_open(self, position: Position) -> None:
        """포지션 OPEN 기록"""
        pass

    @abstractmethod
    def log_position_close(self, position: Position) -> None:
        """포지션 CLOSE 기록"""
        pass

    @abstractmethod
    def log_order(self, leg: OrderLeg) -> None:
        """주문 레그 기록"""
        pass

    @abstractmethod
    def log_error(self, message: str) -> None:
        """에러 로그 기록"""
        pass

    @abstractmethod
    def load_positions(self) -> List[Position]:
        """저장된 포지션 로드"""
        pass


class CsvStorage(BaseStorage):
    """Minimal file-based storage for spreads/trades."""

    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.spreads_file = self.data_dir / "spreads.csv"
        self.positions_file = self.data_dir / "positions.csv"
        self.trades_file = self.data_dir / "trades.csv"
        self.orders_file = self.data_dir / "orders.csv"
        self.errors_file = self.data_dir / "errors.log"

    def _append_csv(self, path: Path, headers: list[str], row: dict) -> None:
        file_exists = path.exists()
        with path.open("a", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=headers)
            if not file_exists:
                writer.writeheader()
            writer.writerow(row)

    def log_spread(self, opportunity: SpreadOpportunity) -> None:
        headers = [
            "timestamp",
            "symbol",
            "upbit_price",
            "binance_price",
            "binance_price_krw",
            "spread_pct",
            "net_spread_pct",
            "is_opportunity",
        ]
        row = {
            "timestamp": opportunity.timestamp,
            "symbol": opportunity.symbol,
            "upbit_price": opportunity.upbit_price,
            "binance_price": opportunity.binance_price,
            "binance_price_krw": opportunity.binance_price_krw,
            "spread_pct": opportunity.spread_pct,
            "net_spread_pct": opportunity.net_spread_pct,
            "is_opportunity": opportunity.is_opportunity,
        }
        self._append_csv(self.spreads_file, headers, row)

    def log_position_open(self, position: Position) -> None:
        """포지션 OPEN 시 positions.csv에 행 추가"""
        headers = [
            "timestamp_open",
            "symbol",
            "direction",
            "size",
            "entry_upbit_price",
            "entry_binance_price",
            "entry_spread_pct",
            "timestamp_close",
            "exit_upbit_price",
            "exit_binance_price",
            "exit_spread_pct",
            "pnl_krw",
            "pnl_pct",
            "status",
        ]
        row = {
            "timestamp_open": position.timestamp_open.isoformat(),
            "symbol": position.symbol,
            "direction": position.direction,
            "size": position.size,
            "entry_upbit_price": position.entry_upbit_price,
            "entry_binance_price": position.entry_binance_price,
            "entry_spread_pct": position.entry_spread_pct,
            "timestamp_close": "",
            "exit_upbit_price": "",
            "exit_binance_price": "",
            "exit_spread_pct": "",
            "pnl_krw": "",
            "pnl_pct": "",
            "status": position.status,
        }
        self._append_csv(self.positions_file, headers, row)

    def log_position_close(self, position: Position) -> None:
        """포지션 CLOSE 시 positions.csv에 CLOSED 행 추가 및 trades.csv에 체결 기록 추가"""
        # positions.csv에 CLOSED 상태로 행 추가
        headers = [
            "timestamp_open",
            "symbol",
            "direction",
            "size",
            "entry_upbit_price",
            "entry_binance_price",
            "entry_spread_pct",
            "timestamp_close",
            "exit_upbit_price",
            "exit_binance_price",
            "exit_spread_pct",
            "pnl_krw",
            "pnl_pct",
            "status",
        ]
        row = {
            "timestamp_open": position.timestamp_open.isoformat(),
            "symbol": position.symbol,
            "direction": position.direction,
            "size": position.size,
            "entry_upbit_price": position.entry_upbit_price,
            "entry_binance_price": position.entry_binance_price,
            "entry_spread_pct": position.entry_spread_pct,
            "timestamp_close": position.timestamp_close.isoformat() if position.timestamp_close else "",
            "exit_upbit_price": position.exit_upbit_price if position.exit_upbit_price else "",
            "exit_binance_price": position.exit_binance_price if position.exit_binance_price else "",
            "exit_spread_pct": position.exit_spread_pct if position.exit_spread_pct else "",
            "pnl_krw": position.pnl_krw if position.pnl_krw is not None else "",
            "pnl_pct": position.pnl_pct if position.pnl_pct is not None else "",
            "status": position.status,
        }
        self._append_csv(self.positions_file, headers, row)
        
        # trades.csv에 체결 기록 추가
        self._log_trade_record(position)

    def _log_trade_record(self, position: Position) -> None:
        """trades.csv에 체결 기록 추가 (OPEN/CLOSE 각 1행)"""
        headers = [
            "timestamp",
            "symbol",
            "direction",
            "size",
            "price",
            "side",
            "pnl_krw",
            "pnl_pct",
        ]
        rows = [
            {
                "timestamp": position.timestamp_open.isoformat(),
                "symbol": position.symbol,
                "direction": position.direction,
                "size": position.size,
                "price": f"{position.entry_upbit_price}/{position.entry_binance_price}",
                "side": "OPEN",
                "pnl_krw": "",
                "pnl_pct": "",
            },
        ]
        if position.timestamp_close:
            rows.append(
                {
                    "timestamp": position.timestamp_close.isoformat(),
                    "symbol": position.symbol,
                    "direction": position.direction,
                    "size": position.size,
                    "price": f"{position.exit_upbit_price}/{position.exit_binance_price}",
                    "side": "CLOSE",
                    "pnl_krw": position.pnl_krw if position.pnl_krw is not None else "",
                    "pnl_pct": position.pnl_pct if position.pnl_pct is not None else "",
                }
            )
        for row in rows:
            self._append_csv(self.trades_file, headers, row)

    def log_order(self, leg: OrderLeg) -> None:
        """주문 레그 기록 (logs/orders.csv에 append)
        
        Args:
            leg: OrderLeg 객체 (Order Routing & Slippage Model)
        """
        headers = [
            "timestamp",
            "symbol",
            "venue",
            "side",
            "qty",
            "price_theoretical",
            "price_effective",
            "slippage_bps",
            "order_id",
            "leg_id",
        ]
        row = {
            "timestamp": leg.timestamp.isoformat(),
            "symbol": leg.symbol,
            "venue": leg.venue,
            "side": leg.side,
            "qty": leg.qty,
            "price_theoretical": leg.price_theoretical,
            "price_effective": leg.price_effective if leg.price_effective is not None else "",
            "slippage_bps": leg.slippage_bps if leg.slippage_bps is not None else "",
            "order_id": leg.order_id if leg.order_id is not None else "",
            "leg_id": leg.leg_id,
        }
        self._append_csv(self.orders_file, headers, row)

    def log_error(self, message: str) -> None:
        timestamp = datetime.now(timezone.utc).isoformat()
        with self.errors_file.open("a", encoding="utf-8") as fh:
            fh.write(f"[{timestamp}] {message}\n")

    def load_positions(self) -> List[Position]:
        """positions.csv에서 포지션 로드"""
        positions = []
        if not self.positions_file.exists():
            return positions
        with self.positions_file.open("r", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                try:
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
                    positions.append(pos)
                except (ValueError, KeyError) as e:
                    self.log_error(f"Failed to load position from CSV: {e}")
        return positions


class PostgresStorage(BaseStorage):
    """PostgreSQL/TimescaleDB 기반 저장소 (PHASE D – MODULE D1)
    
    PostgreSQL/TimescaleDB를 사용한 시계열 데이터 저장소 구현.
    
    [특징]
    
    1. **psycopg2 기반 동기 구현**:
       - 단일 커넥션 사용 (향후 연결 풀로 확장 가능)
       - 트랜잭션 기반 안정성
    
    2. **테이블 스키마** (docs/DB_SCHEMA.md 참조):
       - positions: 포지션 진입/청산 정보
       - orders: 주문 레그 정보
       - spreads: 스프레드 기회 스냅샷
       - trades: 거래 내역
       - fx_rates: 환율 정보
    
    3. **자동 테이블 생성**:
       - 초기화 시 필요한 테이블 자동 생성
       - 이미 존재하면 스킵
    
    4. **에러 처리**:
       - DB 연결 실패 시 명확한 로그 출력
       - 쿼리 실행 실패 시 예외 발생 (상위에서 처리)
    """

    def __init__(self, config: Dict):
        """
        Args:
            config: 설정 딕셔너리 (config.storage.postgres 섹션)
        
        Raises:
            ImportError: psycopg2가 설치되지 않은 경우
            psycopg2.OperationalError: DB 연결 실패
        """
        try:
            import psycopg2
            from psycopg2 import sql
        except ImportError:
            logger.error(
                "psycopg2 is not installed. "
                "Install it with: pip install psycopg2-binary"
            )
            raise ImportError("psycopg2 is required for PostgresStorage")
        
        self.psycopg2 = psycopg2
        self.sql = sql
        
        self.dsn = config.get("dsn", "postgresql://arbitrage:arbitrage@localhost:5432/arbitrage")
        self.schema = config.get("schema", "public")
        self.enable_timescale = config.get("enable_timescale", False)
        
        # DB 연결 테스트 및 테이블 초기화
        try:
            self.conn = self.psycopg2.connect(self.dsn)
            self.conn.autocommit = True
            logger.info(f"[PostgresStorage] Connected to {self.dsn}")
            self._init_tables()
        except self.psycopg2.OperationalError as e:
            logger.error(f"[PostgresStorage] Failed to connect to DB: {e}")
            raise

    def _init_tables(self) -> None:
        """필요한 테이블 자동 생성"""
        cursor = self.conn.cursor()
        try:
            # positions 테이블
            cursor.execute(f"""
                CREATE TABLE IF NOT EXISTS {self.schema}.positions (
                    id BIGSERIAL PRIMARY KEY,
                    symbol VARCHAR(10) NOT NULL,
                    direction VARCHAR(50) NOT NULL,
                    size NUMERIC(18, 8) NOT NULL,
                    entry_upbit_price NUMERIC(18, 2) NOT NULL,
                    entry_binance_price NUMERIC(18, 8) NOT NULL,
                    entry_spread_pct NUMERIC(8, 4) NOT NULL,
                    exit_upbit_price NUMERIC(18, 2),
                    exit_binance_price NUMERIC(18, 8),
                    exit_spread_pct NUMERIC(8, 4),
                    pnl_krw NUMERIC(18, 2),
                    pnl_pct NUMERIC(8, 4),
                    status VARCHAR(20) NOT NULL DEFAULT 'OPEN',
                    timestamp_open TIMESTAMPTZ NOT NULL,
                    timestamp_close TIMESTAMPTZ,
                    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # orders 테이블
            cursor.execute(f"""
                CREATE TABLE IF NOT EXISTS {self.schema}.orders (
                    id BIGSERIAL PRIMARY KEY,
                    position_id BIGINT REFERENCES {self.schema}.positions(id) ON DELETE CASCADE,
                    symbol VARCHAR(10) NOT NULL,
                    venue VARCHAR(50) NOT NULL,
                    side VARCHAR(20) NOT NULL,
                    qty NUMERIC(18, 8) NOT NULL,
                    price_theoretical NUMERIC(18, 8) NOT NULL,
                    price_effective NUMERIC(18, 8),
                    slippage_bps NUMERIC(8, 2),
                    leg_id VARCHAR(100) NOT NULL,
                    order_id VARCHAR(100),
                    timestamp TIMESTAMPTZ NOT NULL,
                    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # spreads 테이블
            cursor.execute(f"""
                CREATE TABLE IF NOT EXISTS {self.schema}.spreads (
                    id BIGSERIAL PRIMARY KEY,
                    symbol VARCHAR(10) NOT NULL,
                    upbit_price NUMERIC(18, 2) NOT NULL,
                    binance_price NUMERIC(18, 8) NOT NULL,
                    binance_price_krw NUMERIC(18, 2) NOT NULL,
                    spread_pct NUMERIC(8, 4) NOT NULL,
                    net_spread_pct NUMERIC(8, 4) NOT NULL,
                    is_opportunity BOOLEAN NOT NULL DEFAULT FALSE,
                    timestamp TIMESTAMPTZ NOT NULL,
                    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # trades 테이블
            cursor.execute(f"""
                CREATE TABLE IF NOT EXISTS {self.schema}.trades (
                    id BIGSERIAL PRIMARY KEY,
                    position_id BIGINT REFERENCES {self.schema}.positions(id) ON DELETE CASCADE,
                    symbol VARCHAR(10) NOT NULL,
                    direction VARCHAR(50) NOT NULL,
                    size NUMERIC(18, 8) NOT NULL,
                    side VARCHAR(20) NOT NULL,
                    price_upbit NUMERIC(18, 2),
                    price_binance NUMERIC(18, 8),
                    pnl_krw NUMERIC(18, 2),
                    pnl_pct NUMERIC(8, 4),
                    timestamp TIMESTAMPTZ NOT NULL,
                    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # fx_rates 테이블
            cursor.execute(f"""
                CREATE TABLE IF NOT EXISTS {self.schema}.fx_rates (
                    id BIGSERIAL PRIMARY KEY,
                    pair VARCHAR(20) NOT NULL,
                    rate NUMERIC(18, 8) NOT NULL,
                    source VARCHAR(50),
                    timestamp TIMESTAMPTZ NOT NULL,
                    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # 인덱스 생성
            cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_positions_symbol ON {self.schema}.positions(symbol)")
            cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_positions_status ON {self.schema}.positions(status)")
            cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_positions_timestamp_open ON {self.schema}.positions(timestamp_open DESC)")
            cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_orders_symbol ON {self.schema}.orders(symbol)")
            cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_orders_timestamp ON {self.schema}.orders(timestamp DESC)")
            cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_spreads_symbol ON {self.schema}.spreads(symbol)")
            cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_spreads_timestamp ON {self.schema}.spreads(timestamp DESC)")
            
            logger.info("[PostgresStorage] Tables initialized successfully")
        except self.psycopg2.Error as e:
            logger.error(f"[PostgresStorage] Failed to initialize tables: {e}")
            raise
        finally:
            cursor.close()

    def log_spread(self, opportunity: SpreadOpportunity) -> None:
        """스프레드 기회 기록"""
        cursor = self.conn.cursor()
        try:
            cursor.execute(f"""
                INSERT INTO {self.schema}.spreads
                (symbol, upbit_price, binance_price, binance_price_krw, spread_pct, net_spread_pct, is_opportunity, timestamp)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                opportunity.symbol,
                opportunity.upbit_price,
                opportunity.binance_price,
                opportunity.binance_price_krw,
                opportunity.spread_pct,
                opportunity.net_spread_pct,
                opportunity.is_opportunity,
                datetime.fromtimestamp(opportunity.timestamp / 1000, tz=timezone.utc)
            ))
            self.conn.commit()
        except self.psycopg2.Error as e:
            logger.error(f"[PostgresStorage] Failed to log spread: {e}")
            self.conn.rollback()
            raise
        finally:
            cursor.close()

    def log_position_open(self, position: Position) -> None:
        """포지션 OPEN 기록"""
        cursor = self.conn.cursor()
        try:
            cursor.execute(f"""
                INSERT INTO {self.schema}.positions
                (symbol, direction, size, entry_upbit_price, entry_binance_price, entry_spread_pct, status, timestamp_open)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                position.symbol,
                position.direction,
                position.size,
                position.entry_upbit_price,
                position.entry_binance_price,
                position.entry_spread_pct,
                "OPEN",
                position.timestamp_open
            ))
            self.conn.commit()
        except self.psycopg2.Error as e:
            logger.error(f"[PostgresStorage] Failed to log position open: {e}")
            self.conn.rollback()
            raise
        finally:
            cursor.close()

    def log_position_close(self, position: Position) -> None:
        """포지션 CLOSE 기록"""
        cursor = self.conn.cursor()
        try:
            # 기존 포지션 업데이트 (timestamp_open 기준으로 찾기)
            cursor.execute(f"""
                UPDATE {self.schema}.positions
                SET exit_upbit_price = %s,
                    exit_binance_price = %s,
                    exit_spread_pct = %s,
                    pnl_krw = %s,
                    pnl_pct = %s,
                    status = %s,
                    timestamp_close = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE symbol = %s AND direction = %s AND status = 'OPEN'
                ORDER BY timestamp_open DESC
                LIMIT 1
            """, (
                position.exit_upbit_price,
                position.exit_binance_price,
                position.exit_spread_pct,
                position.pnl_krw,
                position.pnl_pct,
                "CLOSED",
                position.timestamp_close,
                position.symbol,
                position.direction
            ))
            self.conn.commit()
        except self.psycopg2.Error as e:
            logger.error(f"[PostgresStorage] Failed to log position close: {e}")
            self.conn.rollback()
            raise
        finally:
            cursor.close()

    def log_order(self, leg: OrderLeg) -> None:
        """주문 레그 기록"""
        cursor = self.conn.cursor()
        try:
            cursor.execute(f"""
                INSERT INTO {self.schema}.orders
                (symbol, venue, side, qty, price_theoretical, price_effective, slippage_bps, leg_id, order_id, timestamp)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                leg.symbol,
                leg.venue,
                leg.side,
                leg.qty,
                leg.price_theoretical,
                leg.price_effective,
                leg.slippage_bps,
                leg.leg_id,
                leg.order_id,
                leg.timestamp
            ))
            self.conn.commit()
        except self.psycopg2.Error as e:
            logger.error(f"[PostgresStorage] Failed to log order: {e}")
            self.conn.rollback()
            raise
        finally:
            cursor.close()

    def log_error(self, message: str) -> None:
        """에러 로그 기록"""
        logger.error(f"[PostgresStorage] {message}")

    def load_positions(self) -> List[Position]:
        """저장된 포지션 로드"""
        positions = []
        cursor = self.conn.cursor()
        try:
            cursor.execute(f"""
                SELECT symbol, direction, size, entry_upbit_price, entry_binance_price, entry_spread_pct,
                       exit_upbit_price, exit_binance_price, exit_spread_pct, pnl_krw, pnl_pct,
                       status, timestamp_open, timestamp_close
                FROM {self.schema}.positions
                ORDER BY timestamp_open DESC
            """)
            
            for row in cursor.fetchall():
                (symbol, direction, size, entry_upbit_price, entry_binance_price, entry_spread_pct,
                 exit_upbit_price, exit_binance_price, exit_spread_pct, pnl_krw, pnl_pct,
                 status, timestamp_open, timestamp_close) = row
                
                pos = Position(
                    symbol=symbol,
                    direction=direction,
                    size=float(size),
                    entry_upbit_price=float(entry_upbit_price),
                    entry_binance_price=float(entry_binance_price),
                    entry_spread_pct=float(entry_spread_pct),
                    timestamp_open=timestamp_open,
                    status=status
                )
                
                if exit_upbit_price is not None:
                    pos.exit_upbit_price = float(exit_upbit_price)
                if exit_binance_price is not None:
                    pos.exit_binance_price = float(exit_binance_price)
                if exit_spread_pct is not None:
                    pos.exit_spread_pct = float(exit_spread_pct)
                if pnl_krw is not None:
                    pos.pnl_krw = float(pnl_krw)
                if pnl_pct is not None:
                    pos.pnl_pct = float(pnl_pct)
                if timestamp_close is not None:
                    pos.timestamp_close = timestamp_close
                
                positions.append(pos)
        except self.psycopg2.Error as e:
            logger.error(f"[PostgresStorage] Failed to load positions: {e}")
        finally:
            cursor.close()
        
        return positions


class RedisCacheStorage:
    """Redis 기반 캐시/헬스 상태 저장 헬퍼 (PHASE D 예정)
    
    TODO (PHASE D – Persistence & Infra):
    ─────────────────────────────────────────────────────────────────────
    Redis를 사용한 실시간 캐시 및 헬스 상태 저장.
    
    [사용 계획]
    
    1. **FX 캐시**:
       - Key: fx:usdkrw
       - Value: float (환율)
       - TTL: config.fx.ttl_seconds
    
    2. **스프레드 스냅샷**:
       - Key: spreads:{symbol}:last
       - Value: JSON (SpreadOpportunity)
       - TTL: 60초
    
    3. **헬스 상태**:
       - Key: health:collector, health:paper, health:live
       - Value: timestamp (마지막 heartbeat)
       - TTL: 10초 (heartbeat 주기)
    
    4. **메트릭 집계** (향후):
       - Key: metrics:daily_pnl:{date}
       - Value: JSON (일일 PnL 요약)
    ─────────────────────────────────────────────────────────────────────
    """

    def __init__(self, config: Dict):
        """
        Args:
            config: 설정 딕셔너리 (config.storage.redis 섹션)
        """
        self.url = config.get("url", "redis://localhost:6379/0")
        self.prefix = config.get("prefix", "arbitrage")
        logger.warning(
            "RedisCacheStorage is not implemented in PHASE C4. "
            "Implementation scheduled for PHASE D."
        )

    def set_fx_rate(self, pair: str, rate: float, ttl: int = 3) -> None:
        """환율 캐시 저장 (예: pair='USDKRW')"""
        raise NotImplementedError(
            "RedisCacheStorage.set_fx_rate() is reserved for PHASE D – Persistence & Infra"
        )

    def get_fx_rate(self, pair: str) -> Optional[float]:
        """환율 캐시 조회"""
        raise NotImplementedError(
            "RedisCacheStorage.get_fx_rate() is reserved for PHASE D – Persistence & Infra"
        )

    def set_spread_snapshot(self, symbol: str, snapshot: Dict) -> None:
        """스프레드 스냅샷 저장"""
        raise NotImplementedError(
            "RedisCacheStorage.set_spread_snapshot() is reserved for PHASE D – Persistence & Infra"
        )

    def get_spread_snapshot(self, symbol: str) -> Optional[Dict]:
        """스프레드 스냅샷 조회"""
        raise NotImplementedError(
            "RedisCacheStorage.get_spread_snapshot() is reserved for PHASE D – Persistence & Infra"
        )

    def set_health_heartbeat(self, component: str) -> None:
        """헬스 상태 heartbeat 기록 (component: 'collector', 'paper', 'live')"""
        raise NotImplementedError(
            "RedisCacheStorage.set_health_heartbeat() is reserved for PHASE D – Persistence & Infra"
        )


def get_storage(config: Dict) -> BaseStorage:
    """저장소 팩토리 함수 (PHASE D – MODULE D1)
    
    config.storage.backend 설정값에 따라 적절한 저장소 인스턴스를 반환합니다.
    
    Args:
        config: 전체 설정 딕셔너리
    
    Returns:
        BaseStorage: 저장소 인스턴스 (CsvStorage, PostgresStorage 등)
    
    Note:
        - backend: "csv" → CsvStorage (기본, 항상 사용 가능)
        - backend: "postgres" → PostgresStorage (psycopg2 필요, DB 연결 필요)
        - backend: "hybrid" → PostgresStorage + CsvStorage fallback (PHASE D2 예정)
        - 연결 실패 시 자동으로 CSV로 fallback
    """
    storage_cfg = config.get("storage", {})
    backend = storage_cfg.get("backend", "csv")
    
    if backend == "csv":
        return CsvStorage(config.get("data_dir", "data"))
    
    elif backend == "postgres":
        try:
            postgres_cfg = storage_cfg.get("postgres", {})
            return PostgresStorage(postgres_cfg)
        except ImportError as e:
            logger.warning(
                f"[WARN] PostgreSQL backend initialization failed: {e}. "
                "Falling back to CSV storage. Install psycopg2-binary to use PostgreSQL."
            )
            return CsvStorage(config.get("data_dir", "data"))
        except Exception as e:
            logger.warning(
                f"[WARN] PostgreSQL backend connection failed: {e}. "
                "Falling back to CSV storage."
            )
            return CsvStorage(config.get("data_dir", "data"))
    
    elif backend == "hybrid":
        logger.warning(
            "[WARN] Hybrid (CSV + Redis) backend is not implemented in PHASE D1. "
            "Falling back to CSV storage. Implementation scheduled for PHASE D2."
        )
        return CsvStorage(config.get("data_dir", "data"))
    
    else:
        logger.warning(
            f"[WARN] Unknown storage backend '{backend}'. Falling back to CSV storage."
        )
        return CsvStorage(config.get("data_dir", "data"))


# ============================================================================
# 하위 호환성: SimpleStorage 별칭
# ============================================================================

SimpleStorage = CsvStorage
"""
하위 호환성을 위한 별칭.
기존 코드에서 SimpleStorage를 사용하는 경우, CsvStorage로 자동 변환됩니다.
"""
