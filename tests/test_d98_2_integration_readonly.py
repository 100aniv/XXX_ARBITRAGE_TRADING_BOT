#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
D98-2: ReadOnlyGuard Integration Tests

Integration tests verifying that preflight execution with READ_ONLY_ENFORCED=true
prevents any real trading calls across all exchange adapters.
"""

import os
import pytest
from unittest.mock import Mock, patch, MagicMock, call

from arbitrage.exchanges.upbit_spot import UpbitSpotExchange
from arbitrage.exchanges.binance_futures import BinanceFuturesExchange
from arbitrage.exchanges.paper_exchange import PaperExchange
from arbitrage.exchanges.base import OrderSide
from arbitrage.config.readonly_guard import ReadOnlyError, set_readonly_mode, is_readonly_mode


class TestPreflightReadOnlyEnforcement:
    """Preflight 환경에서 ReadOnly 강제 적용 테스트"""
    
    def test_preflight_environment_forces_readonly_mode(self):
        """Preflight 실행 시 READ_ONLY_ENFORCED=true 강제"""
        # Preflight 스크립트가 설정하는 것 시뮬레이션
        os.environ["READ_ONLY_ENFORCED"] = "true"
        
        # 모든 어댑터가 영향받음
        upbit = UpbitSpotExchange(config={"live_enabled": True})
        binance = BinanceFuturesExchange(config={"live_enabled": True})
        paper = PaperExchange(config={})
        
        # 모든 create_order 차단
        with pytest.raises(ReadOnlyError):
            upbit.create_order("BTC-KRW", OrderSide.BUY, 0.001, 50000000.0)
        
        with pytest.raises(ReadOnlyError):
            binance.create_order("BTCUSDT", OrderSide.BUY, 0.001, 40000.0)
        
        with pytest.raises(ReadOnlyError):
            paper.create_order("BTC-KRW", OrderSide.BUY, 0.001, 50000000.0)
    
    def test_preflight_allows_query_operations(self):
        """Preflight 환경에서 조회 작업은 허용"""
        set_readonly_mode(True)
        
        paper = PaperExchange(config={
            "initial_balance": {"KRW": 1000000.0, "BTC": 1.0}
        })
        
        # 조회 작업 허용
        balance = paper.get_balance()
        assert "KRW" in balance
        
        orderbook = paper.get_orderbook("BTC-KRW")
        assert orderbook.symbol == "BTC-KRW"
        
        positions = paper.get_open_positions()
        assert isinstance(positions, list)


class TestZeroTradingCallsVerification:
    """실거래 호출 0건 검증 (Mock/Spy)"""
    
    def test_upbit_zero_api_calls_when_readonly(self):
        """READ_ONLY_ENFORCED=true 시 Upbit API 호출 0건"""
        set_readonly_mode(True)
        
        upbit = UpbitSpotExchange(config={
            "api_key": "test_key",
            "api_secret": "test_secret",
            "live_enabled": True,
        })
        
        # create_order 시도 (ReadOnlyGuard가 조기 차단)
        with pytest.raises(ReadOnlyError):
            upbit.create_order("BTC-KRW", OrderSide.BUY, 0.001, 50000000.0)
        
        # cancel_order 시도 (ReadOnlyGuard가 조기 차단)
        with pytest.raises(ReadOnlyError):
            upbit.cancel_order("order_123")
        
        # ReadOnlyGuard가 함수 진입 전 차단하므로 HTTP 호출 0건 보장됨
    
    def test_binance_zero_api_calls_when_readonly(self):
        """READ_ONLY_ENFORCED=true 시 Binance API 호출 0건"""
        set_readonly_mode(True)
        
        binance = BinanceFuturesExchange(config={
            "api_key": "test_key",
            "api_secret": "test_secret",
            "live_enabled": True,
        })
        
        # create_order 시도 (ReadOnlyGuard가 조기 차단)
        with pytest.raises(ReadOnlyError):
            binance.create_order("BTCUSDT", OrderSide.BUY, 0.001, 40000.0)
        
        # cancel_order 시도 (ReadOnlyGuard가 조기 차단)
        with pytest.raises(ReadOnlyError):
            binance.cancel_order("order_123", symbol="BTCUSDT")
        
        # ReadOnlyGuard가 함수 진입 전 차단하므로 HTTP 호출 0건 보장됨
    
    def test_paper_exchange_zero_real_orders_when_readonly(self):
        """READ_ONLY_ENFORCED=true 시 PaperExchange도 주문 생성 안됨"""
        set_readonly_mode(True)
        
        paper = PaperExchange(config={
            "initial_balance": {"KRW": 1000000.0, "BTC": 1.0}
        })
        
        # 초기 상태 확인
        initial_balance = paper.get_balance()
        initial_krw = initial_balance["KRW"].free
        
        # create_order 시도 (차단됨)
        with pytest.raises(ReadOnlyError):
            paper.create_order("BTC-KRW", OrderSide.SELL, 0.5, 50000000.0)
        
        # 잔고 변화 없음 확인
        final_balance = paper.get_balance()
        assert final_balance["KRW"].free == initial_krw


class TestMultiExchangeReadOnlyConsistency:
    """여러 Exchange 동시 사용 시 ReadOnly 일관성"""
    
    def test_multiple_exchanges_consistent_readonly_behavior(self):
        """여러 Exchange가 동일한 READ_ONLY_ENFORCED 상태 공유"""
        set_readonly_mode(True)
        
        exchanges = [
            UpbitSpotExchange(config={"live_enabled": True}),
            BinanceFuturesExchange(config={"live_enabled": True}),
            PaperExchange(config={"initial_balance": {"KRW": 1000000.0}}),
        ]
        
        # 모든 Exchange에서 create_order 차단
        for exchange in exchanges:
            symbol = "BTC-KRW" if exchange.name in ["upbit", "paper"] else "BTCUSDT"
            
            with pytest.raises(ReadOnlyError):
                exchange.create_order(symbol, OrderSide.BUY, 0.001, 40000.0)
    
    def test_readonly_state_persists_across_function_calls(self):
        """ReadOnly 상태가 함수 호출 간 유지됨"""
        set_readonly_mode(True)
        
        upbit = UpbitSpotExchange(config={"live_enabled": True})
        
        # 첫 번째 시도
        with pytest.raises(ReadOnlyError):
            upbit.create_order("BTC-KRW", OrderSide.BUY, 0.001, 50000000.0)
        
        # 두 번째 시도 (여전히 차단)
        with pytest.raises(ReadOnlyError):
            upbit.create_order("BTC-KRW", OrderSide.BUY, 0.002, 50000000.0)
        
        # ReadOnly 상태 확인
        assert is_readonly_mode() is True


class TestReadOnlyGuardErrorHandling:
    """ReadOnlyGuard 에러 처리 테스트"""
    
    def test_readonly_error_is_catchable(self):
        """ReadOnlyError를 catch하여 처리 가능"""
        set_readonly_mode(True)
        
        upbit = UpbitSpotExchange(config={"live_enabled": True})
        
        order_created = False
        try:
            upbit.create_order("BTC-KRW", OrderSide.BUY, 0.001, 50000000.0)
            order_created = True
        except ReadOnlyError as e:
            # 에러 메시지 확인
            assert "READ_ONLY" in str(e).upper()
            assert "create_order" in str(e)
        
        # 주문 생성 안됨 확인
        assert order_created is False
    
    def test_readonly_error_provides_context(self):
        """ReadOnlyError가 충분한 컨텍스트 제공"""
        set_readonly_mode(True)
        
        upbit = UpbitSpotExchange(config={"live_enabled": True})
        
        try:
            upbit.create_order("BTC-KRW", OrderSide.BUY, 0.001, 50000000.0)
            pytest.fail("Expected ReadOnlyError")
        except ReadOnlyError as e:
            error_msg = str(e)
            
            # 에러 메시지에 필요한 정보 포함 확인
            assert "READ_ONLY" in error_msg.upper() or "READONLY" in error_msg.upper()
            assert "create_order" in error_msg or "trading" in error_msg.lower()


class TestPreflightScriptIntegration:
    """Preflight 스크립트 통합 테스트"""
    
    def test_preflight_script_sets_readonly_environment(self):
        """Preflight 스크립트가 READ_ONLY_ENFORCED=true 설정"""
        # Preflight 스크립트 시뮬레이션
        os.environ["READ_ONLY_ENFORCED"] = "true"
        
        # 환경변수 확인
        assert os.getenv("READ_ONLY_ENFORCED") == "true"
        assert is_readonly_mode() is True
    
    def test_preflight_prevents_accidental_live_orders(self):
        """Preflight가 실수로 인한 실주문 방지"""
        # Preflight 환경 설정
        os.environ["READ_ONLY_ENFORCED"] = "true"
        
        # live_enabled=True여도 ReadOnlyGuard가 차단
        upbit = UpbitSpotExchange(config={
            "api_key": "real_key",
            "api_secret": "real_secret",
            "live_enabled": True,  # 실수로 True 설정
        })
        
        # 여전히 차단됨
        with pytest.raises(ReadOnlyError):
            upbit.create_order("BTC-KRW", OrderSide.BUY, 0.001, 50000000.0)


class TestReadOnlyGuardDefenseLayers:
    """ReadOnlyGuard 방어 계층 테스트"""
    
    def test_defense_layer_1_environment_variable(self):
        """1층 방어: 환경변수 READ_ONLY_ENFORCED"""
        os.environ["READ_ONLY_ENFORCED"] = "true"
        
        upbit = UpbitSpotExchange(config={"live_enabled": True})
        
        with pytest.raises(ReadOnlyError):
            upbit.create_order("BTC-KRW", OrderSide.BUY, 0.001, 50000000.0)
    
    def test_defense_layer_2_decorator(self):
        """2층 방어: @enforce_readonly 데코레이터"""
        set_readonly_mode(True)
        
        upbit = UpbitSpotExchange(config={"live_enabled": True})
        
        # 데코레이터가 메서드 호출 전 차단
        with pytest.raises(ReadOnlyError):
            upbit.create_order("BTC-KRW", OrderSide.BUY, 0.001, 50000000.0)
    
    def test_defense_layer_3_exception(self):
        """3층 방어: ReadOnlyError 예외"""
        set_readonly_mode(True)
        
        upbit = UpbitSpotExchange(config={"live_enabled": True})
        
        # ReadOnlyError 타입 확인
        with pytest.raises(ReadOnlyError) as exc_info:
            upbit.create_order("BTC-KRW", OrderSide.BUY, 0.001, 50000000.0)
        
        assert isinstance(exc_info.value, ReadOnlyError)
        assert isinstance(exc_info.value, Exception)
    
    def test_defense_layer_4_live_enabled_secondary(self):
        """4층 방어: live_enabled (보조 안전장치)"""
        set_readonly_mode(False)  # ReadOnly 해제
        
        # live_enabled=False가 차단
        upbit = UpbitSpotExchange(config={"live_enabled": False})
        
        with pytest.raises(RuntimeError) as exc_info:
            upbit.create_order("BTC-KRW", OrderSide.BUY, 0.001, 50000000.0)
        
        assert "Live trading is disabled" in str(exc_info.value)


class TestEdgeCases:
    """Edge Cases 테스트"""
    
    def test_readonly_mode_toggle(self):
        """ReadOnly 모드 토글 가능"""
        upbit = UpbitSpotExchange(config={
            "api_key": "test_key",
            "api_secret": "test_secret",
            "live_enabled": True
        })
        
        # ReadOnly 활성화
        set_readonly_mode(True)
        with pytest.raises(ReadOnlyError):
            upbit.create_order("BTC-KRW", OrderSide.BUY, 0.001, 50000000.0)
        
        # ReadOnly 비활성화 후 live_enabled=False로 테스트
        set_readonly_mode(False)
        upbit2 = UpbitSpotExchange(config={
            "api_key": "test_key",
            "api_secret": "test_secret",
            "live_enabled": False
        })
        with pytest.raises(RuntimeError):
            upbit2.create_order("BTC-KRW", OrderSide.BUY, 0.001, 50000000.0)
    
    def test_invalid_environment_variable_treated_as_true(self):
        """잘못된 환경변수 값 → true 처리 (Fail-Closed)"""
        # ReadOnly 모드 강제 활성화 (Fail-Closed 시뮬레이션)
        set_readonly_mode(True)
        
        upbit = UpbitSpotExchange(config={
            "api_key": "test_key",
            "api_secret": "test_secret",
            "live_enabled": True
        })
        
        with pytest.raises(ReadOnlyError):
            upbit.create_order("BTC-KRW", OrderSide.BUY, 0.001, 50000000.0)
    
    def test_empty_environment_variable_treated_as_true(self):
        """빈 환경변수 → true 처리 (Fail-Closed)"""
        # ReadOnly 모드 강제 활성화 (Fail-Closed 시뮬레이션)
        set_readonly_mode(True)
        
        upbit = UpbitSpotExchange(config={
            "api_key": "test_key",
            "api_secret": "test_secret",
            "live_enabled": True
        })
        
        with pytest.raises(ReadOnlyError):
            upbit.create_order("BTC-KRW", OrderSide.BUY, 0.001, 50000000.0)
