# -*- coding: utf-8 -*-
"""
D80-0: Multi-Currency Support - Domain Tests

Currency, Money, FxRateProvider 기본 동작 테스트.

Test Coverage:
- Currency Enum 속성
- Money 객체 생성/연산
- Money 같은 통화 연산
- Money 다른 통화 연산 금지
- Money 변환 (convert_to)
- StaticFxRateProvider 환율 조회
- Money 반올림
- Money 포맷팅
"""

import pytest
from decimal import Decimal

from arbitrage.common.currency import (
    Currency,
    Money,
    StaticFxRateProvider,
)


# =============================================================================
# Currency Enum Tests
# =============================================================================

class TestCurrency:
    """Currency Enum 기본 동작 테스트"""
    
    def test_currency_enum_values(self):
        """Currency Enum 값 확인"""
        assert Currency.KRW.value == "KRW"
        assert Currency.USD.value == "USD"
        assert Currency.USDT.value == "USDT"
        assert Currency.BTC.value == "BTC"
        assert Currency.ETH.value == "ETH"
    
    def test_currency_decimal_places(self):
        """통화별 소수점 자릿수 확인"""
        assert Currency.KRW.decimal_places == 0
        assert Currency.USD.decimal_places == 2
        assert Currency.USDT.decimal_places == 2
        assert Currency.BTC.decimal_places == 8
        assert Currency.ETH.decimal_places == 6
    
    def test_currency_symbol(self):
        """통화별 기호 확인"""
        assert Currency.KRW.symbol == "₩"
        assert Currency.USD.symbol == "$"
        assert Currency.USDT.symbol == "₮"
        assert Currency.BTC.symbol == "₿"
        assert Currency.ETH.symbol == "Ξ"


# =============================================================================
# Money Creation & Properties Tests
# =============================================================================

class TestMoneyCreation:
    """Money 객체 생성 테스트"""
    
    def test_money_creation_with_decimal(self):
        """Decimal로 Money 생성"""
        money = Money(Decimal("1000"), Currency.KRW)
        
        assert money.amount == Decimal("1000")
        assert money.currency == Currency.KRW
    
    def test_money_creation_with_int(self):
        """int로 Money 생성 (auto-convert to Decimal)"""
        money = Money(1000, Currency.USD)
        
        assert money.amount == Decimal("1000")
        assert money.currency == Currency.USD
    
    def test_money_creation_with_float(self):
        """float로 Money 생성 (auto-convert to Decimal)"""
        money = Money(1000.50, Currency.USDT)
        
        # float → Decimal 변환 시 정확도 유지
        assert money.amount == Decimal("1000.5")
        assert money.currency == Currency.USDT
    
    def test_money_creation_invalid_currency(self):
        """잘못된 currency 타입으로 생성 시 TypeError"""
        with pytest.raises(TypeError, match="currency must be Currency Enum"):
            Money(Decimal("1000"), "KRW")  # str은 불가
    
    def test_money_properties(self):
        """Money 속성 (is_zero, is_positive, is_negative) 테스트"""
        zero = Money(Decimal("0"), Currency.KRW)
        positive = Money(Decimal("100"), Currency.KRW)
        negative = Money(Decimal("-50"), Currency.KRW)
        
        assert zero.is_zero is True
        assert zero.is_positive is False
        assert zero.is_negative is False
        
        assert positive.is_zero is False
        assert positive.is_positive is True
        assert positive.is_negative is False
        
        assert negative.is_zero is False
        assert negative.is_positive is False
        assert negative.is_negative is True


# =============================================================================
# Money Arithmetic Tests (같은 통화)
# =============================================================================

class TestMoneySameCurrencyArithmetic:
    """같은 통화끼리 연산 테스트"""
    
    def test_money_addition(self):
        """덧셈"""
        m1 = Money(Decimal("1000"), Currency.KRW)
        m2 = Money(Decimal("500"), Currency.KRW)
        
        result = m1 + m2
        
        assert result.amount == Decimal("1500")
        assert result.currency == Currency.KRW
    
    def test_money_subtraction(self):
        """뺄셈"""
        m1 = Money(Decimal("1000"), Currency.KRW)
        m2 = Money(Decimal("300"), Currency.KRW)
        
        result = m1 - m2
        
        assert result.amount == Decimal("700")
        assert result.currency == Currency.KRW
    
    def test_money_multiplication_by_scalar(self):
        """스칼라 곱셈"""
        money = Money(Decimal("100"), Currency.USD)
        
        result = money * 3
        
        assert result.amount == Decimal("300")
        assert result.currency == Currency.USD
    
    def test_money_multiplication_reverse(self):
        """역방향 스칼라 곱셈 (3 * money)"""
        money = Money(Decimal("100"), Currency.USD)
        
        result = 3 * money
        
        assert result.amount == Decimal("300")
        assert result.currency == Currency.USD
    
    def test_money_division_by_scalar(self):
        """스칼라 나눗셈"""
        money = Money(Decimal("1000"), Currency.KRW)
        
        result = money / 4
        
        assert result.amount == Decimal("250")
        assert result.currency == Currency.KRW
    
    def test_money_division_by_money(self):
        """Money / Money → 비율 (Decimal)"""
        m1 = Money(Decimal("1000"), Currency.KRW)
        m2 = Money(Decimal("250"), Currency.KRW)
        
        ratio = m1 / m2
        
        assert ratio == Decimal("4")
        assert isinstance(ratio, Decimal)
    
    def test_money_negation(self):
        """부호 반전"""
        money = Money(Decimal("100"), Currency.KRW)
        
        result = -money
        
        assert result.amount == Decimal("-100")
        assert result.currency == Currency.KRW
    
    def test_money_abs(self):
        """절댓값"""
        negative = Money(Decimal("-100"), Currency.KRW)
        
        result = abs(negative)
        
        assert result.amount == Decimal("100")
        assert result.currency == Currency.KRW


# =============================================================================
# Money Arithmetic Tests (다른 통화 - 금지)
# =============================================================================

class TestMoneyDifferentCurrencyArithmetic:
    """다른 통화끼리 연산 금지 테스트"""
    
    def test_money_addition_different_currency_fails(self):
        """다른 통화 덧셈 시 ValueError"""
        krw = Money(Decimal("1000"), Currency.KRW)
        usd = Money(Decimal("1"), Currency.USD)
        
        with pytest.raises(ValueError, match="Cannot add different currencies"):
            krw + usd
    
    def test_money_subtraction_different_currency_fails(self):
        """다른 통화 뺄셈 시 ValueError"""
        krw = Money(Decimal("1000"), Currency.KRW)
        usd = Money(Decimal("1"), Currency.USD)
        
        with pytest.raises(ValueError, match="Cannot subtract different currencies"):
            krw - usd
    
    def test_money_division_different_currency_fails(self):
        """다른 통화 나눗셈 시 ValueError"""
        krw = Money(Decimal("1000"), Currency.KRW)
        usd = Money(Decimal("1"), Currency.USD)
        
        with pytest.raises(ValueError, match="Cannot divide different currencies"):
            krw / usd


# =============================================================================
# Money Comparison Tests
# =============================================================================

class TestMoneyComparison:
    """Money 비교 연산 테스트"""
    
    def test_money_comparison_same_currency(self):
        """같은 통화 비교"""
        m1 = Money(Decimal("100"), Currency.KRW)
        m2 = Money(Decimal("200"), Currency.KRW)
        m3 = Money(Decimal("100"), Currency.KRW)
        
        assert m1 < m2
        assert m1 <= m2
        assert m1 <= m3
        assert m2 > m1
        assert m2 >= m1
        assert m1 >= m3
    
    def test_money_comparison_different_currency_fails(self):
        """다른 통화 비교 시 ValueError"""
        krw = Money(Decimal("1000"), Currency.KRW)
        usd = Money(Decimal("1"), Currency.USD)
        
        with pytest.raises(ValueError, match="Cannot compare different currencies"):
            krw < usd


# =============================================================================
# Money Conversion Tests
# =============================================================================

class TestMoneyConversion:
    """Money 통화 변환 테스트"""
    
    def test_money_convert_to_same_currency(self):
        """같은 통화로 변환 시 그대로 반환"""
        fx = StaticFxRateProvider({})
        money = Money(Decimal("1000"), Currency.KRW)
        
        result = money.convert_to(Currency.KRW, fx)
        
        assert result is money  # Same object
    
    def test_money_convert_usd_to_krw(self):
        """USD → KRW 변환"""
        fx = StaticFxRateProvider({
            (Currency.USD, Currency.KRW): Decimal("1420.50"),
        })
        
        usd = Money(Decimal("10"), Currency.USD)
        krw = usd.convert_to(Currency.KRW, fx)
        
        assert krw.amount == Decimal("14205.0")  # 10 * 1420.50
        assert krw.currency == Currency.KRW
    
    def test_money_convert_krw_to_usd_reverse_rate(self):
        """KRW → USD 변환 (역환율 자동 계산)"""
        fx = StaticFxRateProvider({
            (Currency.USD, Currency.KRW): Decimal("1420.50"),
        })
        
        krw = Money(Decimal("1420.50"), Currency.KRW)
        usd = krw.convert_to(Currency.USD, fx)
        
        # 1420.50 KRW / 1420.50 ≈ 1 USD (Decimal 정밀도 고려)
        # Decimal 나눗셈 결과가 정확히 1.0이 아닐 수 있음
        assert abs(usd.amount - Decimal("1.0")) < Decimal("0.000001")  # 소수점 6자리 이내
        assert usd.currency == Currency.USD
    
    def test_money_convert_usdt_to_krw(self):
        """USDT → KRW 변환"""
        fx = StaticFxRateProvider({
            (Currency.USDT, Currency.KRW): Decimal("1500.00"),
        })
        
        usdt = Money(Decimal("100"), Currency.USDT)
        krw = usdt.convert_to(Currency.KRW, fx)
        
        assert krw.amount == Decimal("150000.00")
        assert krw.currency == Currency.KRW
    
    def test_money_convert_no_rate_fails(self):
        """환율이 없는 경우 ValueError"""
        fx = StaticFxRateProvider({})
        
        usd = Money(Decimal("1"), Currency.USD)
        
        with pytest.raises(ValueError, match="No FX rate found"):
            usd.convert_to(Currency.KRW, fx)


# =============================================================================
# Money Rounding Tests
# =============================================================================

class TestMoneyRounding:
    """Money 반올림 테스트"""
    
    def test_money_round_krw(self):
        """KRW 반올림 (정수)"""
        money = Money(Decimal("1420.567"), Currency.KRW)
        
        rounded = money.round()
        
        assert rounded.amount == Decimal("1421")
        assert rounded.currency == Currency.KRW
    
    def test_money_round_usd(self):
        """USD 반올림 (센트 단위)"""
        money = Money(Decimal("1.4567"), Currency.USD)
        
        rounded = money.round()
        
        assert rounded.amount == Decimal("1.46")
        assert rounded.currency == Currency.USD
    
    def test_money_round_btc(self):
        """BTC 반올림 (사토시 단위)"""
        money = Money(Decimal("0.123456789"), Currency.BTC)
        
        rounded = money.round()
        
        assert rounded.amount == Decimal("0.12345679")
        assert rounded.currency == Currency.BTC


# =============================================================================
# Money Formatting Tests
# =============================================================================

class TestMoneyFormatting:
    """Money 포맷팅 테스트"""
    
    def test_money_str_krw(self):
        """KRW str() 포맷"""
        money = Money(Decimal("1000000"), Currency.KRW)
        
        assert str(money) == "₩1,000,000"
    
    def test_money_str_usd(self):
        """USD str() 포맷"""
        money = Money(Decimal("1234.56"), Currency.USD)
        
        assert str(money) == "$1,234.56"
    
    def test_money_str_btc(self):
        """BTC str() 포맷"""
        money = Money(Decimal("0.12345678"), Currency.BTC)
        
        assert str(money) == "₿0.12345678"
    
    def test_money_repr(self):
        """Money repr() 포맷"""
        money = Money(Decimal("1000"), Currency.KRW)
        
        # repr은 코드로 재생성 가능한 형태
        assert repr(money) == 'Money(Decimal("1000"), Currency.KRW)'


# =============================================================================
# StaticFxRateProvider Tests
# =============================================================================

class TestStaticFxRateProvider:
    """StaticFxRateProvider 테스트"""
    
    def test_fx_provider_same_currency(self):
        """같은 통화 환율은 1.0"""
        fx = StaticFxRateProvider({})
        
        rate = fx.get_rate(Currency.KRW, Currency.KRW)
        
        assert rate == Decimal("1.0")
    
    def test_fx_provider_forward_rate(self):
        """Forward rate 조회"""
        fx = StaticFxRateProvider({
            (Currency.USD, Currency.KRW): Decimal("1420.50"),
        })
        
        rate = fx.get_rate(Currency.USD, Currency.KRW)
        
        assert rate == Decimal("1420.50")
    
    def test_fx_provider_reverse_rate(self):
        """Reverse rate 조회 (역환율 자동 계산)"""
        fx = StaticFxRateProvider({
            (Currency.USD, Currency.KRW): Decimal("1420.50"),
        })
        
        rate = fx.get_rate(Currency.KRW, Currency.USD)
        
        # 1 / 1420.50 ≈ 0.000704
        expected = Decimal("1.0") / Decimal("1420.50")
        assert rate == expected
    
    def test_fx_provider_no_rate_fails(self):
        """환율이 없는 경우 ValueError"""
        fx = StaticFxRateProvider({})
        
        with pytest.raises(ValueError, match="No FX rate found"):
            fx.get_rate(Currency.USD, Currency.KRW)
    
    def test_fx_provider_updated_at(self):
        """업데이트 시각 조회"""
        import time
        
        before = time.time()
        fx = StaticFxRateProvider({
            (Currency.USD, Currency.KRW): Decimal("1420.50"),
        })
        after = time.time()
        
        updated_at = fx.get_updated_at(Currency.USD, Currency.KRW)
        
        # 생성 시각 범위 내
        assert before <= updated_at <= after


# =============================================================================
# Integration Test (종합)
# =============================================================================

class TestCurrencyIntegration:
    """종합 통합 테스트"""
    
    def test_cross_exchange_pnl_calculation(self):
        """
        Cross-Exchange PnL 계산 시나리오.
        
        Upbit KRW 마켓: +50,000 KRW 수익
        Binance USDT 마켓: -30 USDT 손실
        
        → Base Currency (KRW)로 통합 집계
        """
        # FX Rate: 1 USDT = 1500 KRW
        fx = StaticFxRateProvider({
            (Currency.USDT, Currency.KRW): Decimal("1500.00"),
        })
        
        # Upbit PnL
        upbit_pnl_krw = Money(Decimal("50000"), Currency.KRW)
        
        # Binance PnL (USDT)
        binance_pnl_usdt = Money(Decimal("-30"), Currency.USDT)
        
        # USDT → KRW 변환
        binance_pnl_krw = binance_pnl_usdt.convert_to(Currency.KRW, fx)
        
        # 총 PnL (KRW 기준)
        total_pnl_krw = upbit_pnl_krw + binance_pnl_krw
        
        # 50,000 + (-30 * 1500) = 50,000 - 45,000 = 5,000 KRW
        assert total_pnl_krw.amount == Decimal("5000")
        assert total_pnl_krw.currency == Currency.KRW
    
    def test_multi_currency_balance_aggregation(self):
        """
        다중 통화 잔고 집계 시나리오.
        
        Upbit: 10,000,000 KRW
        Binance: 7,000 USDT
        
        → KRW 기준으로 총 잔고 계산
        """
        fx = StaticFxRateProvider({
            (Currency.USDT, Currency.KRW): Decimal("1500.00"),
        })
        
        upbit_balance = Money(Decimal("10000000"), Currency.KRW)
        binance_balance = Money(Decimal("7000"), Currency.USDT)
        
        # USDT → KRW 변환
        binance_balance_krw = binance_balance.convert_to(Currency.KRW, fx)
        
        # 총 잔고
        total_balance_krw = upbit_balance + binance_balance_krw
        
        # 10,000,000 + (7,000 * 1500) = 10,000,000 + 10,500,000 = 20,500,000 KRW
        assert total_balance_krw.amount == Decimal("20500000")
        assert total_balance_krw.currency == Currency.KRW
        
        # Exposure ratio 계산 (Upbit 비율)
        upbit_ratio = upbit_balance / total_balance_krw
        
        # 10,000,000 / 20,500,000 ≈ 0.4878
        assert 0.48 < upbit_ratio < 0.49


# =============================================================================
# Import Test
# =============================================================================

def test_currency_import():
    """arbitrage.common.currency import 테스트"""
    from arbitrage.common.currency import Currency, Money, StaticFxRateProvider, FxRateProvider
    
    assert Currency is not None
    assert Money is not None
    assert StaticFxRateProvider is not None
    assert FxRateProvider is not None
