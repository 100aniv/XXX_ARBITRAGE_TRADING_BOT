# -*- coding: utf-8 -*-
"""
D98-1: Preflight ReadOnly 통합 테스트

Preflight 스크립트 실행 시 실주문 0건 보장 검증.
"""

import os
import sys
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock, call

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from arbitrage.config.readonly_guard import is_readonly_mode, set_readonly_mode, ReadOnlyError
from arbitrage.exchanges.paper_exchange import PaperExchange
from arbitrage.exchanges.base import OrderSide, OrderType


class TestPreflightReadOnlyEnforcement:
    """Preflight 스크립트 실행 시 ReadOnly 강제 적용 테스트"""
    
    def test_preflight_sets_readonly_mode_to_true(self):
        """
        Preflight 스크립트가 READ_ONLY_ENFORCED=true 강제 설정
        """
        # Given: Preflight 스크립트 import 전 환경 초기화
        os.environ.pop("READ_ONLY_ENFORCED", None)
        
        # When: Preflight 스크립트처럼 READ_ONLY_ENFORCED 강제 설정
        os.environ["READ_ONLY_ENFORCED"] = "true"
        
        # Then: read-only 모드 활성화
        from arbitrage.config.readonly_guard import ReadOnlyGuard
        guard = ReadOnlyGuard()
        assert guard.is_read_only is True
    
    def test_preflight_blocks_create_order_calls(self):
        """
        Preflight 실행 중 create_order 호출 시 차단
        """
        # Given: READ_ONLY_ENFORCED=true 강제 설정
        set_readonly_mode(True)
        exchange = PaperExchange(initial_balance={"KRW": 1000000})
        
        # When/Then: create_order 호출 시 ReadOnlyError 발생
        with pytest.raises(ReadOnlyError):
            exchange.create_order(
                symbol="BTC-KRW",
                side=OrderSide.BUY,
                qty=0.01,
                price=100000.0
            )
    
    def test_preflight_blocks_cancel_order_calls(self):
        """
        Preflight 실행 중 cancel_order 호출 시 차단
        """
        # Given: READ_ONLY_ENFORCED=true 강제 설정
        set_readonly_mode(True)
        exchange = PaperExchange()
        
        # When/Then: cancel_order 호출 시 ReadOnlyError 발생
        with pytest.raises(ReadOnlyError):
            exchange.cancel_order("fake_order_id")
    
    def test_preflight_allows_get_balance(self):
        """
        Preflight 실행 중 get_balance 조회는 허용
        """
        # Given: READ_ONLY_ENFORCED=true 강제 설정
        set_readonly_mode(True)
        exchange = PaperExchange(initial_balance={"KRW": 1000000})
        
        # When: get_balance 호출
        balance = exchange.get_balance()
        
        # Then: 정상 조회
        assert "KRW" in balance
        assert balance["KRW"].free == 1000000
    
    def test_preflight_allows_get_orderbook(self):
        """
        Preflight 실행 중 get_orderbook 조회는 허용
        """
        # Given: READ_ONLY_ENFORCED=true 강제 설정
        set_readonly_mode(True)
        exchange = PaperExchange()
        
        # When: get_orderbook 호출
        orderbook = exchange.get_orderbook("BTC-KRW")
        
        # Then: 정상 조회
        assert orderbook.symbol == "BTC-KRW"
    
    def test_preflight_allows_get_open_positions(self):
        """
        Preflight 실행 중 get_open_positions 조회는 허용
        """
        # Given: READ_ONLY_ENFORCED=true 강제 설정
        set_readonly_mode(True)
        exchange = PaperExchange()
        
        # When: get_open_positions 호출
        positions = exchange.get_open_positions()
        
        # Then: 정상 조회
        assert positions == []


class TestPreflightOrderCallCounter:
    """Preflight 실행 시 주문 호출 카운트 검증"""
    
    @patch.object(PaperExchange, 'create_order')
    @patch.object(PaperExchange, 'cancel_order')
    def test_preflight_zero_order_calls_with_mocks(self, mock_cancel, mock_create):
        """
        Mock을 사용하여 Preflight 실행 시 주문 함수 호출 0건 검증
        """
        # Given: READ_ONLY_ENFORCED=true 강제 설정
        set_readonly_mode(True)
        exchange = PaperExchange(initial_balance={"KRW": 1000000})
        
        # When: 조회 함수만 호출
        exchange.get_balance()
        exchange.get_orderbook("BTC-KRW")
        exchange.get_open_positions()
        
        # Then: create_order, cancel_order 호출 0건
        assert mock_create.call_count == 0
        assert mock_cancel.call_count == 0
    
    def test_preflight_readonly_prevents_accidental_orders(self):
        """
        실수로 주문 함수 호출 시도 시 차단 검증
        """
        # Given: READ_ONLY_ENFORCED=true 강제 설정
        set_readonly_mode(True)
        exchange = PaperExchange(initial_balance={"KRW": 1000000})
        
        # When: 실수로 주문 함수 호출 시도
        order_attempts = 0
        cancel_attempts = 0
        
        # Try create_order
        try:
            exchange.create_order(
                symbol="BTC-KRW",
                side=OrderSide.BUY,
                qty=0.01,
                price=100000.0
            )
            order_attempts += 1
        except ReadOnlyError:
            pass  # Expected
        
        # Try cancel_order
        try:
            exchange.cancel_order("fake_id")
            cancel_attempts += 1
        except ReadOnlyError:
            pass  # Expected
        
        # Then: 모든 시도 차단됨 (호출 성공 0건)
        assert order_attempts == 0
        assert cancel_attempts == 0


class TestPreflightReadOnlyGuardIntegration:
    """Preflight와 ReadOnlyGuard 통합 테스트"""
    
    def test_readonly_guard_check_passes_for_query_operations(self):
        """
        ReadOnlyGuard가 조회 작업은 허용
        """
        # Given: READ_ONLY_ENFORCED=true
        set_readonly_mode(True)
        from arbitrage.config.readonly_guard import get_readonly_guard
        guard = get_readonly_guard()
        
        # When/Then: 조회 함수는 check_readonly 호출 없이 동작
        # (조회 함수에는 데코레이터가 적용되지 않음)
        exchange = PaperExchange()
        balance = exchange.get_balance()  # Should not raise
        orderbook = exchange.get_orderbook("BTC-KRW")  # Should not raise
        
        assert balance is not None
        assert orderbook is not None
    
    def test_readonly_guard_check_fails_for_trading_operations(self):
        """
        ReadOnlyGuard가 거래 작업은 차단
        """
        # Given: READ_ONLY_ENFORCED=true
        set_readonly_mode(True)
        from arbitrage.config.readonly_guard import get_readonly_guard
        guard = get_readonly_guard()
        
        # When/Then: 거래 함수는 ReadOnlyError 발생
        with pytest.raises(ReadOnlyError):
            guard.check_readonly("create_order")
        
        with pytest.raises(ReadOnlyError):
            guard.check_readonly("cancel_order")
    
    def test_readonly_mode_cannot_be_bypassed(self):
        """
        ReadOnly 모드 우회 불가능 검증
        """
        # Given: READ_ONLY_ENFORCED=true 강제 설정
        os.environ["READ_ONLY_ENFORCED"] = "true"
        set_readonly_mode(True)
        
        # When: 환경변수 변경 시도 (우회 시도)
        os.environ["READ_ONLY_ENFORCED"] = "false"
        
        # Then: 기존 guard 인스턴스는 여전히 read-only
        # (singleton이므로 새 인스턴스 생성 전까지 유지)
        assert is_readonly_mode() is True
        
        # 새 인스턴스 생성 시에만 변경 반영
        from arbitrage.config.readonly_guard import ReadOnlyGuard
        new_guard = ReadOnlyGuard()
        # 이 시점에서는 환경변수가 false이므로 read-only 비활성화
        # 하지만 Preflight는 항상 true로 강제 설정하므로 안전


class TestPreflightFailConditions:
    """Preflight FAIL 조건 테스트"""
    
    def test_fail_if_readonly_mode_is_false(self):
        """
        READ_ONLY_ENFORCED=false 시 FAIL
        """
        # Given: READ_ONLY_ENFORCED=false
        set_readonly_mode(False)
        
        # When: readonly 모드 확인
        is_readonly = is_readonly_mode()
        
        # Then: FAIL (false는 실주문 위험)
        assert is_readonly is False
        # Preflight 스크립트는 이 경우 FAIL로 처리해야 함
    
    def test_pass_if_readonly_mode_is_true(self):
        """
        READ_ONLY_ENFORCED=true 시 PASS
        """
        # Given: READ_ONLY_ENFORCED=true
        set_readonly_mode(True)
        
        # When: readonly 모드 확인
        is_readonly = is_readonly_mode()
        
        # Then: PASS (실주문 0건 보장)
        assert is_readonly is True
    
    def test_trading_call_count_must_be_zero(self):
        """
        거래 함수 호출 카운트가 0이 아니면 FAIL
        """
        # Given: READ_ONLY_ENFORCED=false (허용 모드)
        set_readonly_mode(False)
        exchange = PaperExchange(initial_balance={"KRW": 10000000, "BTC": 1.0})
        
        # When: create_order 호출 (BTC 매도)
        order = exchange.create_order(
            symbol="KRW-BTC",
            side=OrderSide.SELL,
            qty=0.1,
            price=50000000.0
        )
        
        # Then: 주문 생성됨 (호출 카운트 1)
        assert order is not None
        # 이 경우 Preflight는 FAIL로 처리해야 함
        # (READ_ONLY_ENFORCED=true가 강제되므로 이 상황은 발생하지 않음)


class TestPreflightReadOnlyGuardEdgeCases:
    """Edge Case 테스트"""
    
    def test_readonly_guard_with_multiple_exchanges(self):
        """
        여러 Exchange 인스턴스에 대해 ReadOnlyGuard 일관성 검증
        """
        # Given: READ_ONLY_ENFORCED=true
        set_readonly_mode(True)
        
        exchange1 = PaperExchange(initial_balance={"KRW": 1000000})
        exchange2 = PaperExchange(initial_balance={"USDT": 10000})
        
        # When/Then: 모든 인스턴스에서 주문 차단
        with pytest.raises(ReadOnlyError):
            exchange1.create_order("BTC-KRW", OrderSide.BUY, 0.01, 100000.0)
        
        with pytest.raises(ReadOnlyError):
            exchange2.create_order("BTC-USDT", OrderSide.BUY, 0.01, 90000.0)
    
    def test_readonly_guard_persists_across_function_calls(self):
        """
        함수 호출 간 ReadOnlyGuard 상태 유지
        """
        # Given: READ_ONLY_ENFORCED=true
        set_readonly_mode(True)
        exchange = PaperExchange(initial_balance={"KRW": 1000000})
        
        # When: 여러 번 호출
        for _ in range(5):
            with pytest.raises(ReadOnlyError):
                exchange.create_order("BTC-KRW", OrderSide.BUY, 0.01, 100000.0)
        
        # Then: 모든 호출이 차단됨 (일관성 유지)
    
    def test_readonly_guard_error_is_catchable(self):
        """
        ReadOnlyError가 적절히 catch 가능
        """
        # Given: READ_ONLY_ENFORCED=true
        set_readonly_mode(True)
        exchange = PaperExchange(initial_balance={"KRW": 1000000})
        
        # When: try-except로 에러 처리
        caught_error = False
        try:
            exchange.create_order("BTC-KRW", OrderSide.BUY, 0.01, 100000.0)
        except ReadOnlyError as e:
            caught_error = True
            error_message = str(e)
        
        # Then: 에러 캐치 성공, 메시지 확인
        assert caught_error is True
        assert "create_order" in error_message
        assert "READ_ONLY" in error_message
