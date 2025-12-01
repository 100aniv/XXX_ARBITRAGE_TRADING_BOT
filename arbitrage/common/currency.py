# -*- coding: utf-8 -*-
"""
D80-0: Multi-Currency Support - Domain Model

Currency-aware 금액 계산을 위한 도메인 모델.

Features:
- Currency Enum (KRW, USD, USDT, BTC, ETH)
- Money Value Object (amount + currency)
- FxRateProvider Protocol
- StaticFxRateProvider (테스트/개발용)

Architecture:
    Money(amount, currency)
            ↓
    FxRateProvider.get_rate(base, quote)
            ↓
    Money.convert_to(target_currency)

Usage:
    >>> from arbitrage.common.currency import Currency, Money
    >>> krw = Money(Decimal("1000"), Currency.KRW)
    >>> usd = Money(Decimal("1"), Currency.USD)
    >>> 
    >>> # ✅ 같은 통화 연산
    >>> total_krw = krw + Money(Decimal("500"), Currency.KRW)
    >>> 
    >>> # ❌ 다른 통화 직접 연산 금지
    >>> krw + usd  # ValueError
    >>> 
    >>> # ✅ 변환 후 연산
    >>> fx = StaticFxRateProvider({(Currency.USD, Currency.KRW): Decimal("1420.50")})
    >>> usd_in_krw = usd.convert_to(Currency.KRW, fx)
    >>> total_krw = krw + usd_in_krw
"""

import logging
import time
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_EVEN
from enum import Enum
from typing import Dict, Protocol, Tuple, Union

logger = logging.getLogger(__name__)


# =============================================================================
# Currency Enum
# =============================================================================

class Currency(str, Enum):
    """
    지원 통화 목록.
    
    str Enum을 사용하여 JSON serialization, Prometheus label 호환성 확보.
    
    Attributes:
        KRW: 원화 (Upbit 기준통화)
        USD: 달러 (Global standard)
        USDT: 테더 (Stablecoin)
        BTC: 비트코인 (Crypto standard)
        ETH: 이더리움 (향후 확장)
    """
    KRW = "KRW"
    USD = "USD"
    USDT = "USDT"
    BTC = "BTC"
    ETH = "ETH"
    
    @property
    def decimal_places(self) -> int:
        """
        통화별 소수점 자릿수.
        
        Returns:
            소수점 자릿수 (int)
        
        Example:
            >>> Currency.KRW.decimal_places
            0  # 원화는 정수
            >>> Currency.USD.decimal_places
            2  # 센트 단위
        """
        return {
            Currency.KRW: 0,   # 원화는 정수
            Currency.USD: 2,   # 센트 단위
            Currency.USDT: 2,  # 센트 단위
            Currency.BTC: 8,   # 사토시 단위
            Currency.ETH: 6,   # Wei 단위 (간소화)
        }[self]
    
    @property
    def symbol(self) -> str:
        """
        통화 기호.
        
        Returns:
            통화 기호 문자열
        
        Example:
            >>> Currency.KRW.symbol
            '₩'
            >>> Currency.USD.symbol
            '$'
        """
        return {
            Currency.KRW: "₩",
            Currency.USD: "$",
            Currency.USDT: "₮",
            Currency.BTC: "₿",
            Currency.ETH: "Ξ",
        }[self]


# =============================================================================
# Money Value Object
# =============================================================================

@dataclass(frozen=True)
class Money:
    """
    금액 + 통화를 함께 표현하는 Value Object.
    
    Immutable, Type-safe, Currency-aware 연산 지원.
    
    Attributes:
        amount: 금액 (Decimal)
        currency: 통화 (Currency Enum)
    
    Example:
        >>> money = Money(Decimal("1000"), Currency.KRW)
        >>> print(money)
        ₩1,000
        >>> 
        >>> # 같은 통화 연산
        >>> money + Money(Decimal("500"), Currency.KRW)
        Money(Decimal('1500'), Currency.KRW)
        >>> 
        >>> # 다른 통화 연산 금지
        >>> money + Money(Decimal("1"), Currency.USD)
        ValueError: Cannot add different currencies: KRW + USD
    """
    amount: Decimal
    currency: Currency
    
    def __post_init__(self):
        """Validation: amount는 Decimal, currency는 Currency Enum"""
        # Auto-convert to Decimal if needed
        if not isinstance(self.amount, Decimal):
            object.__setattr__(self, 'amount', Decimal(str(self.amount)))
        
        if not isinstance(self.currency, Currency):
            raise TypeError(
                f"currency must be Currency Enum, got {type(self.currency).__name__}"
            )
    
    # =========================================================================
    # Arithmetic Operations (같은 통화끼리만)
    # =========================================================================
    
    def __add__(self, other: 'Money') -> 'Money':
        """
        덧셈 (같은 통화만 허용).
        
        Args:
            other: 더할 Money 객체
        
        Returns:
            합산된 Money 객체
        
        Raises:
            TypeError: other가 Money가 아닌 경우
            ValueError: 다른 통화끼리 연산 시도 시
        """
        if not isinstance(other, Money):
            raise TypeError(f"Cannot add Money with {type(other).__name__}")
        
        if self.currency != other.currency:
            raise ValueError(
                f"Cannot add different currencies: {self.currency.value} + {other.currency.value}. "
                "Use convert_to() first."
            )
        
        return Money(self.amount + other.amount, self.currency)
    
    def __sub__(self, other: 'Money') -> 'Money':
        """
        뺄셈 (같은 통화만 허용).
        
        Args:
            other: 뺄 Money 객체
        
        Returns:
            차감된 Money 객체
        
        Raises:
            TypeError: other가 Money가 아닌 경우
            ValueError: 다른 통화끼리 연산 시도 시
        """
        if not isinstance(other, Money):
            raise TypeError(f"Cannot subtract {type(other).__name__} from Money")
        
        if self.currency != other.currency:
            raise ValueError(
                f"Cannot subtract different currencies: {self.currency.value} - {other.currency.value}. "
                "Use convert_to() first."
            )
        
        return Money(self.amount - other.amount, self.currency)
    
    def __mul__(self, scalar: Union[int, float, Decimal]) -> 'Money':
        """
        스칼라 곱셈.
        
        Args:
            scalar: 곱할 스칼라 값
        
        Returns:
            곱해진 Money 객체
        """
        if isinstance(scalar, (int, float)):
            scalar = Decimal(str(scalar))
        
        return Money(self.amount * scalar, self.currency)
    
    def __rmul__(self, scalar: Union[int, float, Decimal]) -> 'Money':
        """역방향 스칼라 곱셈 (2 * money)"""
        return self.__mul__(scalar)
    
    def __truediv__(self, other: Union['Money', int, float, Decimal]) -> Union['Money', Decimal]:
        """
        나눗셈.
        
        Args:
            other: Money 또는 스칼라
        
        Returns:
            - Money / scalar → Money
            - Money / Money (같은 통화) → Decimal (비율)
        
        Raises:
            ZeroDivisionError: 0으로 나누기 시도 시
            ValueError: 다른 통화끼리 나누기 시도 시
        """
        if isinstance(other, Money):
            # Money / Money → 비율 (Decimal)
            if self.currency != other.currency:
                raise ValueError(
                    f"Cannot divide different currencies: {self.currency.value} / {other.currency.value}"
                )
            
            if other.amount == 0:
                raise ZeroDivisionError("Cannot divide by zero Money")
            
            return self.amount / other.amount
        
        # Money / scalar → Money
        if isinstance(other, (int, float)):
            other = Decimal(str(other))
        
        if other == 0:
            raise ZeroDivisionError("Cannot divide Money by zero")
        
        return Money(self.amount / other, self.currency)
    
    def __neg__(self) -> 'Money':
        """부호 반전"""
        return Money(-self.amount, self.currency)
    
    def __abs__(self) -> 'Money':
        """절댓값"""
        return Money(abs(self.amount), self.currency)
    
    # =========================================================================
    # Comparison (같은 통화끼리만)
    # =========================================================================
    
    def __lt__(self, other: 'Money') -> bool:
        """Less than"""
        if not isinstance(other, Money):
            raise TypeError(f"Cannot compare Money with {type(other).__name__}")
        
        if self.currency != other.currency:
            raise ValueError(
                f"Cannot compare different currencies: {self.currency.value} vs {other.currency.value}"
            )
        
        return self.amount < other.amount
    
    def __le__(self, other: 'Money') -> bool:
        """Less than or equal"""
        if not isinstance(other, Money):
            raise TypeError(f"Cannot compare Money with {type(other).__name__}")
        
        if self.currency != other.currency:
            raise ValueError(
                f"Cannot compare different currencies: {self.currency.value} vs {other.currency.value}"
            )
        
        return self.amount <= other.amount
    
    def __gt__(self, other: 'Money') -> bool:
        """Greater than"""
        if not isinstance(other, Money):
            raise TypeError(f"Cannot compare Money with {type(other).__name__}")
        
        if self.currency != other.currency:
            raise ValueError(
                f"Cannot compare different currencies: {self.currency.value} vs {other.currency.value}"
            )
        
        return self.amount > other.amount
    
    def __ge__(self, other: 'Money') -> bool:
        """Greater than or equal"""
        if not isinstance(other, Money):
            raise TypeError(f"Cannot compare Money with {type(other).__name__}")
        
        if self.currency != other.currency:
            raise ValueError(
                f"Cannot compare different currencies: {self.currency.value} vs {other.currency.value}"
            )
        
        return self.amount >= other.amount
    
    # =========================================================================
    # Conversion & Formatting
    # =========================================================================
    
    def convert_to(self, target_currency: Currency, fx_provider: 'FxRateProvider') -> 'Money':
        """
        다른 통화로 변환.
        
        Args:
            target_currency: 목표 통화
            fx_provider: 환율 제공자
        
        Returns:
            변환된 Money 객체
        
        Example:
            >>> fx = StaticFxRateProvider({(Currency.USD, Currency.KRW): Decimal("1420.50")})
            >>> usd = Money(Decimal("1"), Currency.USD)
            >>> krw = usd.convert_to(Currency.KRW, fx)
            >>> print(krw)
            ₩1,420.50
        """
        if self.currency == target_currency:
            return self  # 같은 통화면 그대로 반환
        
        rate = fx_provider.get_rate(self.currency, target_currency)
        converted_amount = self.amount * rate
        
        return Money(converted_amount, target_currency)
    
    def round(self) -> 'Money':
        """
        통화별 소수점 자릿수로 반올림 (Banker's rounding).
        
        Returns:
            반올림된 Money 객체
        
        Example:
            >>> money = Money(Decimal("1420.567"), Currency.KRW)
            >>> money.round()
            Money(Decimal('1421'), Currency.KRW)
        """
        places = self.currency.decimal_places
        
        if places == 0:
            quantize_str = "1"
        else:
            quantize_str = f"0.{'0' * places}"
        
        rounded_amount = self.amount.quantize(
            Decimal(quantize_str),
            rounding=ROUND_HALF_EVEN  # Banker's rounding
        )
        
        return Money(rounded_amount, self.currency)
    
    def __str__(self) -> str:
        """
        사람이 읽기 쉬운 형식.
        
        Returns:
            포맷된 문자열
        
        Example:
            >>> money = Money(Decimal("1000000"), Currency.KRW)
            >>> str(money)
            '₩1,000,000'
        """
        places = self.currency.decimal_places
        
        # Format with thousands separator
        if places == 0:
            formatted = f"{self.amount:,.0f}"
        else:
            formatted = f"{self.amount:,.{places}f}"
        
        return f"{self.currency.symbol}{formatted}"
    
    def __repr__(self) -> str:
        """
        개발자용 표현.
        
        Returns:
            repr 문자열
        
        Example:
            >>> money = Money(Decimal("1000"), Currency.KRW)
            >>> repr(money)
            'Money(Decimal("1000"), Currency.KRW)'
        """
        return f"Money(Decimal(\"{self.amount}\"), Currency.{self.currency.name})"
    
    # =========================================================================
    # Properties
    # =========================================================================
    
    @property
    def is_zero(self) -> bool:
        """0원인지 확인"""
        return self.amount == Decimal("0")
    
    @property
    def is_positive(self) -> bool:
        """양수인지 확인"""
        return self.amount > Decimal("0")
    
    @property
    def is_negative(self) -> bool:
        """음수인지 확인"""
        return self.amount < Decimal("0")


# =============================================================================
# FxRateProvider Protocol
# =============================================================================

class FxRateProvider(Protocol):
    """
    환율 제공자 인터페이스.
    
    Protocol을 사용하여 Duck Typing 지원.
    """
    
    def get_rate(self, base: Currency, quote: Currency) -> Decimal:
        """
        환율 조회: 1 base = ? quote
        
        Args:
            base: 기준 통화
            quote: 목표 통화
        
        Returns:
            환율 (Decimal)
        
        Example:
            >>> fx.get_rate(Currency.USD, Currency.KRW)
            Decimal("1420.50")  # 1 USD = 1420.50 KRW
        """
        ...
    
    def get_updated_at(self, base: Currency, quote: Currency) -> float:
        """
        환율 업데이트 시각 (Unix timestamp).
        
        Args:
            base: 기준 통화
            quote: 목표 통화
        
        Returns:
            timestamp (초 단위)
        """
        ...


# =============================================================================
# StaticFxRateProvider (테스트/개발용)
# =============================================================================

class StaticFxRateProvider:
    """
    정적 환율 제공자 (테스트/개발용).
    
    고정된 환율 테이블을 메모리에 저장.
    
    Example:
        >>> rates = {
        ...     (Currency.USD, Currency.KRW): Decimal("1420.50"),
        ...     (Currency.USDT, Currency.KRW): Decimal("1500.00"),
        ... }
        >>> fx = StaticFxRateProvider(rates)
        >>> fx.get_rate(Currency.USD, Currency.KRW)
        Decimal('1420.50')
    """
    
    def __init__(self, rates: Dict[Tuple[Currency, Currency], Decimal]):
        """
        Args:
            rates: {(base, quote): rate} 형식의 환율 테이블
        
        Example:
            rates = {
                (Currency.USD, Currency.KRW): Decimal("1420.50"),
                (Currency.USDT, Currency.KRW): Decimal("1500.00"),
                (Currency.BTC, Currency.USD): Decimal("97000.00"),
            }
        """
        self.rates = rates
        self.updated_at = time.time()
        
        logger.debug(
            "[FX_PROVIDER] Initialized StaticFxRateProvider with %d rates",
            len(rates)
        )
    
    def get_rate(self, base: Currency, quote: Currency) -> Decimal:
        """
        환율 조회.
        
        Args:
            base: 기준 통화
            quote: 목표 통화
        
        Returns:
            환율 (Decimal)
        
        Raises:
            ValueError: 환율을 찾을 수 없는 경우
        """
        # 같은 통화
        if base == quote:
            return Decimal("1.0")
        
        # Forward lookup
        if (base, quote) in self.rates:
            return self.rates[(base, quote)]
        
        # Reverse lookup (역환율)
        if (quote, base) in self.rates:
            reverse_rate = self.rates[(quote, base)]
            if reverse_rate == 0:
                raise ValueError(f"Invalid reverse rate: {quote} → {base} = 0")
            return Decimal("1.0") / reverse_rate
        
        # Triangulation (향후 확장: USD를 중개 통화로 사용)
        # 예: KRW → BTC = (KRW → USD) * (USD → BTC)
        # 현재는 미구현, 직접 환율만 지원
        
        raise ValueError(
            f"No FX rate found for {base.value} → {quote.value}. "
            f"Available pairs: {list(self.rates.keys())}"
        )
    
    def get_updated_at(self, base: Currency, quote: Currency) -> float:
        """
        업데이트 시각.
        
        Args:
            base: 기준 통화
            quote: 목표 통화
        
        Returns:
            timestamp (초 단위)
        """
        return self.updated_at
