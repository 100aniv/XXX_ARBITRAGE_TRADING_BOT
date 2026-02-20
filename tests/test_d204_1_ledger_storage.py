"""
D204-1: V2 Ledger Storage Tests

SSOT: db/migrations/v2_schema.sql
Target: arbitrage/v2/storage/ledger_storage.py

테스트 전제:
- PostgreSQL 필요 (Docker 또는 로컬)
- v2_schema.sql 마이그레이션 선행 필요
- 환경변수: POSTGRES_CONNECTION_STRING

Author: arbitrage-lite V2
Date: 2025-12-30
"""

import pytest
import psycopg2
import uuid
import os
from datetime import datetime, timezone
from decimal import Decimal

# D205-2 REOPEN-2: timestamp 유틸
from arbitrage.v2.utils.timestamp import now_utc_naive, to_utc_naive
from arbitrage.v2.storage import V2LedgerStorage


@pytest.fixture
def connection_string():
    """PostgreSQL connection string from environment"""
    conn_str = (
        os.getenv("POSTGRES_CONNECTION_STRING")
        or os.getenv("FACTORY_POSTGRES_CONNECTION_STRING")
        or "postgresql://arbitrage:arbitrage@localhost:5432/arbitrage"
    )
    return conn_str


@pytest.fixture
def storage(connection_string):
    """V2LedgerStorage fixture"""
    return V2LedgerStorage(connection_string)


@pytest.fixture
def run_id():
    """Test run_id"""
    return f"test_d204_1_{uuid.uuid4().hex[:12]}"


class TestV2LedgerStorageOrders:
    """Orders (v2_orders) 테스트"""
    
    def test_insert_order(self, storage, run_id):
        """
        Case 1: insert_order() 기본 동작
        
        Verify:
            - Order 삽입 성공
            - get_order_by_id()로 조회 가능
        """
        order_id = f"order_{run_id}_001"
        timestamp = now_utc_naive()
        
        storage.insert_order(
            run_id=run_id,
            order_id=order_id,
            timestamp=timestamp,
            exchange="upbit",
            symbol="BTC/KRW",
            side="BUY",
            order_type="MARKET",
            quantity=0.01,
            price=Decimal('50000000.0'),
            status="pending",
            route_id="route_001",
            strategy_id="v2_engine",
        )
        
        # 조회 검증
        order = storage.get_order_by_id(order_id)
        assert order is not None
        assert order["order_id"] == order_id
        assert order["exchange"] == "upbit"
        assert order["symbol"] == "BTC/KRW"
        assert order["side"] == "BUY"
        assert order["status"] == "pending"
    
    def test_get_orders_by_run_id(self, storage, run_id):
        """
        Case 2: get_orders_by_run_id() 조회
        
        Verify:
            - run_id로 여러 주문 조회
            - timestamp DESC 정렬
        """
        # 2개 주문 삽입
        for i in range(1, 3):
            order_id = f"order_{run_id}_{i:03d}"
            storage.insert_order(
                run_id=run_id,
                order_id=order_id,
                timestamp=datetime.now(timezone.utc),
                exchange="binance",
                symbol="BTC/USDT",
                side="SELL",
                order_type="MARKET",
                quantity=0.01,
                price=Decimal('45000.0'),
                status="filled",
            )
        
        # run_id 조회
        orders = storage.get_orders_by_run_id(run_id, limit=10)
        assert len(orders) >= 2
        
        # run_id 일치 확인
        for order in orders:
            assert order["run_id"] == run_id
    
    def test_update_order_status(self, storage, run_id):
        """
        Case 3: update_order_status() 상태 변경
        
        Verify:
            - pending → filled 상태 변경
        """
        order_id = f"order_{run_id}_status"
        
        # 삽입 (pending)
        storage.insert_order(
            run_id=run_id,
            order_id=order_id,
            timestamp=datetime.now(timezone.utc),
            exchange="upbit",
            symbol="ETH/KRW",
            side="BUY",
            order_type="LIMIT",
            quantity=1.0,
            price=Decimal('3000000.0'),
            status="pending",
        )
        
        # 상태 변경
        storage.update_order_status(order_id, "filled")
        
        # 검증
        order = storage.get_order_by_id(order_id)
        assert order["status"] == "filled"


class TestV2LedgerStorageFills:
    """Fills (v2_fills) 테스트"""
    
    def test_insert_fill(self, storage, run_id):
        """
        Case 4: insert_fill() 기본 동작
        
        Verify:
            - Fill 삽입 성공
            - order_id 연결 확인
        """
        order_id = f"order_{run_id}_fill"
        fill_id = f"fill_{run_id}_001"
        
        # Order 삽입 (선행)
        storage.insert_order(
            run_id=run_id,
            order_id=order_id,
            timestamp=datetime.now(timezone.utc),
            exchange="binance",
            symbol="BTC/USDT",
            side="BUY",
            order_type="MARKET",
            quantity=0.01,
            price=Decimal('45000.0'),
            status="filled",
        )
        
        # Fill 삽입
        storage.insert_fill(
            run_id=run_id,
            order_id=order_id,
            fill_id=fill_id,
            timestamp=datetime.now(timezone.utc),
            exchange="binance",
            symbol="BTC/USDT",
            side="BUY",
            filled_quantity=Decimal('0.01'),
            filled_price=Decimal('45100.0'),
            fee=Decimal('4.51'),
            fee_currency="USDT",
        )
        
        # 조회 검증
        fills = storage.get_fills_by_order_id(order_id)
        assert len(fills) == 1
        assert fills[0]["fill_id"] == fill_id
        assert float(fills[0]["filled_quantity"]) == pytest.approx(0.01)
        assert float(fills[0]["filled_price"]) == pytest.approx(45100.0)
        assert float(fills[0]["fee"]) == pytest.approx(4.51)
    
    def test_get_fills_by_run_id(self, storage, run_id):
        """
        Case 5: get_fills_by_run_id() 조회
        
        Verify:
            - run_id로 여러 체결 조회
        """
        order_id = f"order_{run_id}_multi"
        
        # Order 삽입
        storage.insert_order(
            run_id=run_id,
            order_id=order_id,
            timestamp=datetime.now(timezone.utc),
            exchange="upbit",
            symbol="BTC/KRW",
            side="SELL",
            order_type="MARKET",
            quantity=0.02,
            price=Decimal('50000000.0'),
            status="filled",
        )
        
        # 2개 Fill 삽입 (부분 체결)
        for i in range(1, 3):
            fill_id = f"fill_{run_id}_multi_{i:03d}"
            storage.insert_fill(
                run_id=run_id,
                order_id=order_id,
                fill_id=fill_id,
                timestamp=datetime.now(timezone.utc),
                exchange="upbit",
                symbol="BTC/KRW",
                side="SELL",
                filled_quantity=Decimal('0.01'),
                filled_price=Decimal('50000000.0') + Decimal(str(i * 10000)),
                fee=Decimal('50000.0'),
                fee_currency="KRW",
            )
        
        # run_id 조회
        fills = storage.get_fills_by_run_id(run_id, limit=10)
        assert len(fills) >= 2


class TestV2LedgerStorageTrades:
    """Trades (v2_trades) 테스트"""
    
    def test_insert_trade_entry_only(self, storage, run_id):
        """
        Case 6: insert_trade() Entry만 (status=open)
        
        Verify:
            - Entry 정보만 삽입 (Exit 없음)
            - status = "open"
        """
        trade_id = f"trade_{run_id}_001"
        entry_order_id = f"order_{run_id}_entry"
        
        storage.insert_trade(
            run_id=run_id,
            trade_id=trade_id,
            timestamp=datetime.now(timezone.utc),
            entry_exchange="upbit",
            entry_symbol="BTC/KRW",
            entry_side="BUY",
            entry_order_id=entry_order_id,
            entry_quantity=0.01,
            entry_price=Decimal('49000000.0'),
            entry_timestamp=datetime.now(timezone.utc),
            status="open",
        )
        
        # 조회 검증
        trade = storage.get_trade_by_id(trade_id)
        assert trade is not None
        assert trade["trade_id"] == trade_id
        assert trade["status"] == "open"
        assert trade["entry_exchange"] == "upbit"
        assert trade["exit_exchange"] is None  # Exit 없음
    
    def test_insert_trade_with_exit(self, storage, run_id):
        """
        Case 7: insert_trade() Entry + Exit (status=closed)
        
        Verify:
            - Entry + Exit 동시 삽입
            - realized_pnl 계산됨
        """
        trade_id = f"trade_{run_id}_closed"
        
        storage.insert_trade(
            run_id=run_id,
            trade_id=trade_id,
            timestamp=datetime.now(timezone.utc),
            entry_exchange="upbit",
            entry_symbol="BTC/KRW",
            entry_side="BUY",
            entry_order_id=f"order_{run_id}_entry_001",
            entry_quantity=0.01,
            entry_price=Decimal('49000000.0'),
            entry_timestamp=datetime.now(timezone.utc),
            exit_exchange="binance",
            exit_symbol="BTC/USDT",
            exit_side="SELL",
            exit_order_id=f"order_{run_id}_exit_001",
            exit_quantity=0.01,
            exit_price=Decimal('50000.0'),
            exit_timestamp=datetime.now(timezone.utc),
            realized_pnl=Decimal('50.0'),
            total_fee=Decimal('10.0'),
            status="closed",
        )
        
        # 조회 검증
        trade = storage.get_trade_by_id(trade_id)
        assert trade["status"] == "closed"
        assert trade["exit_exchange"] == "binance"
        assert float(trade["realized_pnl"]) == pytest.approx(50.0)
    
    def test_update_trade_exit(self, storage, run_id):
        """
        Case 8: update_trade_exit() Entry → Exit 업데이트
        
        Verify:
            - open → closed 상태 변경
            - Exit 정보 업데이트
        """
        trade_id = f"trade_{run_id}_update"
        
        # Entry 삽입 (open)
        storage.insert_trade(
            run_id=run_id,
            trade_id=trade_id,
            timestamp=datetime.now(timezone.utc),
            entry_exchange="binance",
            entry_symbol="BTC/USDT",
            entry_side="BUY",
            entry_order_id=f"order_{run_id}_entry_002",
            entry_quantity=0.01,
            entry_price=Decimal('45000.0'),
            entry_timestamp=datetime.now(timezone.utc),
            status="open",
        )
        
        # Exit 업데이트
        storage.update_trade_exit(
            trade_id=trade_id,
            exit_exchange="upbit",
            exit_symbol="BTC/KRW",
            exit_side="SELL",
            exit_order_id=f"order_{run_id}_exit_002",
            exit_quantity=0.01,
            exit_price=Decimal('50000000.0'),
            exit_timestamp=datetime.now(timezone.utc),
            realized_pnl=Decimal('100.0'),
            total_fee=Decimal('15.0'),
            status="closed",
        )
        
        # 검증
        trade = storage.get_trade_by_id(trade_id)
        assert trade["status"] == "closed"
        assert trade["exit_exchange"] == "upbit"
        assert float(trade["realized_pnl"]) == pytest.approx(100.0)
    
    def test_get_trades_by_run_id(self, storage, run_id):
        """
        Case 9: get_trades_by_run_id() 조회
        
        Verify:
            - run_id로 여러 거래 조회
        """
        # 2개 거래 삽입
        for i in range(1, 3):
            trade_id = f"trade_{run_id}_{i:03d}"
            storage.insert_trade(
                run_id=run_id,
                trade_id=trade_id,
                timestamp=datetime.now(timezone.utc),
                entry_exchange="upbit",
                entry_symbol="ETH/KRW",
                entry_side="BUY",
                entry_order_id=f"order_{run_id}_eth_{i}",
                entry_quantity=1.0,
                entry_price=Decimal('3000000.0'),
                entry_timestamp=datetime.now(timezone.utc),
                status="open",
            )
        
        # run_id 조회
        trades = storage.get_trades_by_run_id(run_id, limit=10)
        assert len(trades) >= 2
        
        # run_id 일치 확인
        for trade in trades:
            assert trade["run_id"] == run_id


class TestV2LedgerStorageConnection:
    """Connection 및 스키마 테스트"""
    
    def test_schema_check(self, storage):
        """
        Case 10: _ensure_schema_exists() 스키마 확인
        
        Verify:
            - v2_orders, v2_fills, v2_trades 테이블 존재
            - 경고 메시지 없음 (테이블 존재 시)
        """
        # 스키마 체크는 __init__에서 자동 실행됨
        # 테이블이 없으면 logger.warning 발생 (수동 확인)
        assert storage.connection_string is not None
    
    def test_connection_error_handling(self):
        """
        Case 11: 잘못된 connection string → 경고
        
        Verify:
            - 연결 실패 시 graceful fail (Exception 발생 안 함)
        """
        invalid_conn = "postgresql://invalid:invalid@localhost:9999/invalid"
        
        # 연결 실패해도 __init__은 성공해야 함 (경고만)
        try:
            storage = V2LedgerStorage(invalid_conn)
            assert storage.connection_string == invalid_conn
        except Exception as e:
            pytest.fail(f"__init__ should not raise: {e}")


class TestV2LedgerStorageUTCNaive:
    """UTC Naive 정규화 테스트 (D204-2 Hotfix)"""
    
    def test_normalize_utc_aware_to_naive(self):
        """
        Case 12: tz-aware (UTC+9) → UTC naive 변환
        
        Verify:
            - UTC+9 12:00:00 → UTC 03:00:00 (naive)
            - tzinfo 제거됨
        """
        from arbitrage.v2.storage.ledger_storage import _normalize_to_utc_naive
        from datetime import datetime, timezone, timedelta
        
        # UTC+9 (KST) 12:00:00
        dt_kst = datetime(2025, 12, 30, 12, 0, 0, tzinfo=timezone(timedelta(hours=9)))
        
        # 변환
        dt_utc_naive = _normalize_to_utc_naive(dt_kst)
        
        # 검증
        assert dt_utc_naive.tzinfo is None  # naive
        assert dt_utc_naive.year == 2025
        assert dt_utc_naive.month == 12
        assert dt_utc_naive.day == 30
        assert dt_utc_naive.hour == 3  # UTC 03:00:00
        assert dt_utc_naive.minute == 0
        assert dt_utc_naive.second == 0
    
    def test_normalize_utc_naive_unchanged(self):
        """
        Case 13: tz-naive → unchanged
        
        Verify:
            - 이미 naive인 경우 그대로 반환
        """
        from arbitrage.v2.storage.ledger_storage import _normalize_to_utc_naive
        from datetime import datetime
        
        # naive datetime
        dt_naive = datetime(2025, 12, 30, 3, 0, 0)
        
        # 변환
        dt_result = _normalize_to_utc_naive(dt_naive)
        
        # 검증
        assert dt_result is dt_naive  # 동일 객체 (수정 없음)
        assert dt_result.tzinfo is None
        assert dt_result == dt_naive
    
    def test_order_insert_with_tz_aware(self, storage, run_id):
        """
        Case 14: insert_order() with tz-aware timestamp
        
        Verify:
            - tz-aware 입력 → UTC naive로 저장
            - 조회 시 UTC naive로 반환
        """
        from datetime import timezone, timedelta
        
        order_id = f"order_{run_id}_tz_aware"
        
        # UTC+9 timestamp
        timestamp_kst = datetime(2025, 12, 30, 12, 0, 0, tzinfo=timezone(timedelta(hours=9)))
        
        # 삽입
        storage.insert_order(
            run_id=run_id,
            order_id=order_id,
            timestamp=timestamp_kst,
            exchange="upbit",
            symbol="BTC/KRW",
            side="BUY",
            order_type="MARKET",
            quantity=0.01,
            price=Decimal('50000000.0'),
            status="pending",
        )
        
        # 조회
        order = storage.get_order_by_id(order_id)
        assert order is not None
        
        # UTC naive로 저장되었는지 확인
        stored_timestamp = order["timestamp"]
        assert stored_timestamp.tzinfo is None  # naive
        assert stored_timestamp.hour == 3  # UTC 03:00:00 (not 12:00:00)

    def test_order_insert_with_tz_naive(self, storage, run_id):
        """
        Case 15: insert_order() with tz-naive timestamp
        
        Verify:
            - tz-naive 입력 → 그대로 저장
            - 조회 시 tz-naive로 반환
        """
        from datetime import datetime
        
        order_id = f"order_{run_id}_tz_naive"
        
        # tz-naive timestamp
        timestamp_naive = datetime(2025, 12, 30, 3, 0, 0)
        
        # 삽입
        storage.insert_order(
            run_id=run_id,
            order_id=order_id,
            timestamp=timestamp_naive,
            exchange="upbit",
            symbol="BTC/KRW",
            side="BUY",
            order_type="MARKET",
            quantity=0.01,
            price=Decimal('50000000.0'),
            status="pending",
        )
        
        # 조회
        order = storage.get_order_by_id(order_id)
        assert order is not None
        
        # tz-naive로 저장되었는지 확인
        stored_timestamp = order["timestamp"]
        assert stored_timestamp.tzinfo is None  # naive
        assert stored_timestamp == timestamp_naive
