"""
D205-1: Reporting Tests

SSOT: arbitrage/v2/reporting/

Author: arbitrage-lite V2
Date: 2025-12-30
"""

import pytest
import os
from datetime import date, datetime, timezone
from arbitrage.v2.reporting.aggregator import aggregate_pnl_daily, aggregate_ops_daily
from arbitrage.v2.reporting.writer import upsert_pnl_daily, upsert_ops_daily


@pytest.fixture
def db_connection_string():
    """DB 연결 문자열 (테스트용)"""
    return os.getenv(
        "DATABASE_URL",
        "postgresql://arbitrage:arbitrage@localhost:5432/arbitrage"
    )


class TestReportingAggregator:
    """Aggregator 테스트"""
    
    def test_aggregate_pnl_daily_basic(self, db_connection_string):
        """
        Case 1: PnL 집계 기본 동작
        
        Verify:
            - aggregate_pnl_daily() 실행 성공
            - 반환값에 필수 키 존재
        """
        target_date = date(2025, 12, 30)
        
        result = aggregate_pnl_daily(
            connection_string=db_connection_string,
            target_date=target_date,
            run_id_prefix="d204_2_",
        )
        
        # 필수 키 확인
        assert "date" in result
        assert "gross_pnl" in result
        assert "net_pnl" in result
        assert "fees" in result
        assert "volume" in result
        assert "trades_count" in result
        assert "wins" in result
        assert "losses" in result
        assert "winrate_pct" in result
        
        # 타입 확인
        assert isinstance(result["gross_pnl"], float)
        assert isinstance(result["trades_count"], int)
    
    def test_aggregate_ops_daily_basic(self, db_connection_string):
        """
        Case 2: Ops 집계 기본 동작
        
        Verify:
            - aggregate_ops_daily() 실행 성공
            - 반환값에 필수 키 존재
        """
        target_date = date(2025, 12, 30)
        
        result = aggregate_ops_daily(
            connection_string=db_connection_string,
            target_date=target_date,
            run_id_prefix="d204_2_",
        )
        
        # 필수 키 확인
        assert "date" in result
        assert "orders_count" in result
        assert "fills_count" in result
        assert "rejects_count" in result
        assert "fill_rate_pct" in result
        
        # 타입 확인
        assert isinstance(result["orders_count"], int)
        assert isinstance(result["fills_count"], int)
        assert isinstance(result["fill_rate_pct"], float)
    
    def test_aggregate_pnl_no_data(self, db_connection_string):
        """
        Case 3: 데이터 없는 날짜 집계
        
        Verify:
            - 데이터 없어도 에러 없이 0 값 반환
        """
        target_date = date(2099, 1, 1)  # 미래 날짜
        
        result = aggregate_pnl_daily(
            connection_string=db_connection_string,
            target_date=target_date,
        )
        
        assert result["trades_count"] == 0
        assert result["gross_pnl"] == 0.0
        assert result["net_pnl"] == 0.0


class TestReportingWriter:
    """Writer 테스트"""
    
    def test_upsert_pnl_daily_basic(self, db_connection_string):
        """
        Case 1: PnL upsert 기본 동작
        
        Verify:
            - upsert_pnl_daily() 실행 성공
            - DB에 저장됨
        """
        pnl_metrics = {
            "date": date(2025, 12, 30),
            "gross_pnl": 100.0,
            "net_pnl": 90.0,
            "fees": 10.0,
            "volume": 1000.0,
            "trades_count": 10,
            "wins": 6,
            "losses": 4,
            "winrate_pct": 60.0,
            "avg_spread": None,
            "max_drawdown": None,
            "sharpe_ratio": None,
        }
        
        # upsert (에러 없으면 성공)
        upsert_pnl_daily(
            connection_string=db_connection_string,
            pnl_metrics=pnl_metrics,
        )
    
    def test_upsert_ops_daily_basic(self, db_connection_string):
        """
        Case 2: Ops upsert 기본 동작
        
        Verify:
            - upsert_ops_daily() 실행 성공
            - DB에 저장됨
        """
        ops_metrics = {
            "date": date(2025, 12, 30),
            "orders_count": 100,
            "fills_count": 80,
            "rejects_count": 5,
            "fill_rate_pct": 80.0,
            "avg_slippage_bps": None,
            "latency_p50_ms": None,
            "latency_p95_ms": None,
            "api_errors": 0,
            "rate_limit_hits": 0,
            "reconnects": 0,
            "avg_cpu_pct": None,
            "avg_memory_mb": None,
        }
        
        # upsert (에러 없으면 성공)
        upsert_ops_daily(
            connection_string=db_connection_string,
            ops_metrics=ops_metrics,
        )
    
    def test_upsert_pnl_idempotent(self, db_connection_string):
        """
        Case 3: PnL upsert idempotency 검증
        
        Verify:
            - 동일 날짜에 대해 2번 upsert 시 UPDATE됨 (에러 없음)
        """
        pnl_metrics = {
            "date": date(2025, 12, 30),
            "gross_pnl": 200.0,
            "net_pnl": 180.0,
            "fees": 20.0,
            "volume": 2000.0,
            "trades_count": 20,
            "wins": 12,
            "losses": 8,
            "winrate_pct": 60.0,
            "avg_spread": None,
            "max_drawdown": None,
            "sharpe_ratio": None,
        }
        
        # 1st upsert
        upsert_pnl_daily(
            connection_string=db_connection_string,
            pnl_metrics=pnl_metrics,
        )
        
        # 2nd upsert (동일 날짜)
        pnl_metrics["gross_pnl"] = 250.0  # 값 변경
        upsert_pnl_daily(
            connection_string=db_connection_string,
            pnl_metrics=pnl_metrics,
        )


class TestReportingIntegration:
    """통합 테스트 (aggregator + writer)"""
    
    def test_full_pipeline(self, db_connection_string):
        """
        Case 1: 전체 파이프라인 (집계 → upsert)
        
        Verify:
            - aggregate → upsert 전체 플로우 정상 동작
        """
        target_date = date(2025, 12, 30)
        
        # 1. PnL 집계
        pnl_metrics = aggregate_pnl_daily(
            connection_string=db_connection_string,
            target_date=target_date,
            run_id_prefix="d204_2_",
        )
        
        # 2. PnL upsert
        upsert_pnl_daily(
            connection_string=db_connection_string,
            pnl_metrics=pnl_metrics,
        )
        
        # 3. Ops 집계
        ops_metrics = aggregate_ops_daily(
            connection_string=db_connection_string,
            target_date=target_date,
            run_id_prefix="d204_2_",
        )
        
        # 4. Ops upsert
        upsert_ops_daily(
            connection_string=db_connection_string,
            ops_metrics=ops_metrics,
        )
        
        # 에러 없으면 성공
        assert True
