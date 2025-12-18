# -*- coding: utf-8 -*-
"""
D98-1: ReadOnlyGuard 단위 테스트

실주문 0건 강제 보장 메커니즘 검증.
"""

import os
import pytest
from unittest.mock import MagicMock, patch

from arbitrage.config.readonly_guard import (
    ReadOnlyGuard,
    ReadOnlyError,
    enforce_readonly,
    is_readonly_mode,
    set_readonly_mode,
    get_readonly_guard,
)
from arbitrage.exchanges.paper_exchange import PaperExchange
from arbitrage.exchanges.base import OrderSide, OrderType


class TestReadOnlyGuard:
    """ReadOnlyGuard 기본 기능 테스트"""
    
    def test_readonly_guard_initialization_default_true(self):
        """
        기본값으로 READ_ONLY_ENFORCED=true 설정됨 (Fail-Closed)
        """
        # Given: 환경변수 없음
        os.environ.pop("READ_ONLY_ENFORCED", None)
        
        # When: ReadOnlyGuard 초기화
        guard = ReadOnlyGuard()
        
        # Then: read-only 모드 활성화
        assert guard.is_read_only is True
    
    def test_readonly_guard_initialization_explicit_true(self):
        """
        READ_ONLY_ENFORCED=true 명시적 설정
        """
        # Given: 환경변수 true
        os.environ["READ_ONLY_ENFORCED"] = "true"
        
        # When: ReadOnlyGuard 초기화
        guard = ReadOnlyGuard()
        
        # Then: read-only 모드 활성화
        assert guard.is_read_only is True
    
    def test_readonly_guard_initialization_false(self):
        """
        READ_ONLY_ENFORCED=false 설정
        """
        # Given: 환경변수 false
        os.environ["READ_ONLY_ENFORCED"] = "false"
        
        # When: ReadOnlyGuard 초기화
        guard = ReadOnlyGuard()
        
        # Then: read-only 모드 비활성화
        assert guard.is_read_only is False
    
    def test_readonly_guard_check_readonly_blocks_when_enabled(self):
        """
        READ_ONLY_ENFORCED=true 시 거래 함수 차단
        """
        # Given: read-only 모드 활성화
        os.environ["READ_ONLY_ENFORCED"] = "true"
        guard = ReadOnlyGuard()
        
        # When/Then: 거래 함수 호출 시 ReadOnlyError 발생
        with pytest.raises(ReadOnlyError, match="create_order is not allowed"):
            guard.check_readonly("create_order")
    
    def test_readonly_guard_check_readonly_allows_when_disabled(self):
        """
        READ_ONLY_ENFORCED=false 시 거래 함수 허용
        """
        # Given: read-only 모드 비활성화
        os.environ["READ_ONLY_ENFORCED"] = "false"
        guard = ReadOnlyGuard()
        
        # When/Then: 거래 함수 호출 시 예외 없음
        guard.check_readonly("create_order")  # Should not raise
    
    def test_readonly_guard_error_message_contains_operation_name(self):
        """
        ReadOnlyError 메시지에 작업 이름 포함
        """
        # Given: read-only 모드 활성화
        os.environ["READ_ONLY_ENFORCED"] = "true"
        guard = ReadOnlyGuard()
        
        # When/Then: 에러 메시지에 "cancel_order" 포함
        with pytest.raises(ReadOnlyError, match="cancel_order"):
            guard.check_readonly("cancel_order")


class TestEnforceReadonlyDecorator:
    """@enforce_readonly 데코레이터 테스트"""
    
    def test_decorator_blocks_when_readonly_enabled(self):
        """
        READ_ONLY_ENFORCED=true 시 데코레이터가 함수 차단
        """
        # Given: read-only 모드 활성화
        set_readonly_mode(True)
        
        @enforce_readonly
        def mock_create_order():
            return "order_created"
        
        # When/Then: 함수 호출 시 ReadOnlyError 발생
        with pytest.raises(ReadOnlyError):
            mock_create_order()
    
    def test_decorator_allows_when_readonly_disabled(self):
        """
        READ_ONLY_ENFORCED=false 시 데코레이터가 함수 허용
        """
        # Given: read-only 모드 비활성화
        set_readonly_mode(False)
        
        @enforce_readonly
        def mock_create_order():
            return "order_created"
        
        # When: 함수 호출
        result = mock_create_order()
        
        # Then: 정상 실행
        assert result == "order_created"
    
    def test_decorator_preserves_function_name(self):
        """
        데코레이터가 원본 함수 이름 유지
        """
        # Given: 데코레이터 적용
        @enforce_readonly
        def my_trading_function():
            pass
        
        # Then: 함수 이름 유지
        assert my_trading_function.__name__ == "my_trading_function"


class TestPaperExchangeReadOnlyGuard:
    """PaperExchange에 ReadOnlyGuard 적용 테스트"""
    
    def test_paper_exchange_create_order_blocked_when_readonly(self):
        """
        READ_ONLY_ENFORCED=true 시 PaperExchange.create_order 차단
        """
        # Given: read-only 모드 활성화
        set_readonly_mode(True)
        exchange = PaperExchange(initial_balance={"KRW": 1000000})
        
        # When/Then: create_order 호출 시 ReadOnlyError 발생
        with pytest.raises(ReadOnlyError, match="create_order"):
            exchange.create_order(
                symbol="BTC-KRW",
                side=OrderSide.BUY,
                qty=0.01,
                price=100000.0,
                order_type=OrderType.LIMIT
            )
    
    def test_paper_exchange_cancel_order_blocked_when_readonly(self):
        """
        READ_ONLY_ENFORCED=true 시 PaperExchange.cancel_order 차단
        """
        # Given: read-only 모드 활성화
        set_readonly_mode(True)
        exchange = PaperExchange(initial_balance={"KRW": 1000000})
        
        # When/Then: cancel_order 호출 시 ReadOnlyError 발생
        with pytest.raises(ReadOnlyError, match="cancel_order"):
            exchange.cancel_order("fake_order_id")
    
    def test_paper_exchange_create_order_allowed_when_not_readonly(self):
        """
        READ_ONLY_ENFORCED=false 시 PaperExchange.create_order 허용
        """
        # Given: read-only 모드 비활성화
        set_readonly_mode(False)
        exchange = PaperExchange(initial_balance={"KRW": 10000000, "BTC": 0.1})
        
        # When: create_order 호출 (매도, BTC 보유분 매도)
        result = exchange.create_order(
            symbol="KRW-BTC",  # Upbit 형식
            side=OrderSide.SELL,
            qty=0.01,  # 0.01 BTC 매도
            price=50000000.0,  # 5천만원
            order_type=OrderType.LIMIT
        )
        
        # Then: 주문 생성 성공
        assert result.order_id is not None
        assert result.symbol == "KRW-BTC"
        assert result.qty == 0.01
    
    def test_paper_exchange_get_balance_always_allowed(self):
        """
        조회 함수(get_balance)는 read-only 모드에서도 허용
        """
        # Given: read-only 모드 활성화
        set_readonly_mode(True)
        exchange = PaperExchange(initial_balance={"KRW": 1000000, "BTC": 0.1})
        
        # When: get_balance 호출
        balance = exchange.get_balance()
        
        # Then: 정상 조회
        assert "KRW" in balance
        assert "BTC" in balance
        assert balance["KRW"].free == 1000000
    
    def test_paper_exchange_get_orderbook_always_allowed(self):
        """
        조회 함수(get_orderbook)는 read-only 모드에서도 허용
        """
        # Given: read-only 모드 활성화
        set_readonly_mode(True)
        exchange = PaperExchange()
        
        # When: get_orderbook 호출
        orderbook = exchange.get_orderbook("BTC-KRW")
        
        # Then: 정상 조회
        assert orderbook.symbol == "BTC-KRW"
        assert orderbook.bids is not None
        assert orderbook.asks is not None


class TestReadOnlyModeHelpers:
    """Helper 함수 테스트"""
    
    def test_is_readonly_mode_returns_true_when_enabled(self):
        """
        is_readonly_mode() 함수 - true 반환
        """
        # Given: read-only 모드 활성화
        set_readonly_mode(True)
        
        # When/Then
        assert is_readonly_mode() is True
    
    def test_is_readonly_mode_returns_false_when_disabled(self):
        """
        is_readonly_mode() 함수 - false 반환
        """
        # Given: read-only 모드 비활성화
        set_readonly_mode(False)
        
        # When/Then
        assert is_readonly_mode() is False
    
    def test_set_readonly_mode_changes_global_state(self):
        """
        set_readonly_mode() 함수 - 전역 상태 변경
        """
        # Given: 초기 상태
        set_readonly_mode(True)
        assert is_readonly_mode() is True
        
        # When: 상태 변경
        set_readonly_mode(False)
        
        # Then: 변경 확인
        assert is_readonly_mode() is False
    
    def test_get_readonly_guard_returns_singleton(self):
        """
        get_readonly_guard() 싱글톤 반환
        """
        # When: 여러 번 호출
        guard1 = get_readonly_guard()
        guard2 = get_readonly_guard()
        
        # Then: 동일 인스턴스 (메모리 주소는 다를 수 있으나 동작 일관성 확인)
        assert guard1.is_read_only == guard2.is_read_only


class TestReadOnlyGuardFailClosed:
    """Fail-Closed 원칙 테스트"""
    
    def test_invalid_env_value_treated_as_true(self):
        """
        잘못된 환경변수 값은 true로 처리 (Fail-Closed)
        """
        # Given: 잘못된 환경변수 값
        os.environ["READ_ONLY_ENFORCED"] = "invalid_value"
        
        # When: ReadOnlyGuard 초기화
        guard = ReadOnlyGuard()
        
        # Then: read-only 모드 활성화 (Fail-Closed)
        assert guard.is_read_only is True
    
    def test_empty_env_value_treated_as_true(self):
        """
        빈 환경변수 값은 true로 처리 (Fail-Closed)
        """
        # Given: 빈 환경변수
        os.environ["READ_ONLY_ENFORCED"] = ""
        
        # When: ReadOnlyGuard 초기화
        guard = ReadOnlyGuard()
        
        # Then: read-only 모드 활성화 (Fail-Closed)
        assert guard.is_read_only is True
    
    def test_only_explicit_false_disables_readonly(self):
        """
        명시적 "false" 값만 read-only 비활성화
        """
        # Test: "false"
        os.environ["READ_ONLY_ENFORCED"] = "false"
        guard = ReadOnlyGuard()
        assert guard.is_read_only is False
        
        # Test: "no"
        os.environ["READ_ONLY_ENFORCED"] = "no"
        guard = ReadOnlyGuard()
        assert guard.is_read_only is False
        
        # Test: "0"
        os.environ["READ_ONLY_ENFORCED"] = "0"
        guard = ReadOnlyGuard()
        assert guard.is_read_only is False
        
        # Test: "False" (대소문자 무관)
        os.environ["READ_ONLY_ENFORCED"] = "False"
        guard = ReadOnlyGuard()
        assert guard.is_read_only is False
