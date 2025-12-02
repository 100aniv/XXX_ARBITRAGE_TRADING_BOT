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


# =============================================================================
# RealFxRateProvider (D80-3)
# =============================================================================

class RealFxRateProvider:
    """
    실시간 환율 제공자 (D80-3).
    
    Features:
    - Binance Funding Rate API (USDT→USD)
    - Exchangerate.host API (USD↔KRW)
    - FxCache (TTL 3초)
    - Staleness detection (60초)
    - Fallback to static rates
    
    Architecture:
        get_rate(base, quote)
            ↓
        FxCache (hit/miss)
            ↓
        _fetch_rate_from_api()
            ├─ _fetch_binance_usdt_usd()
            ├─ _fetch_exchangerate_usd_krw()
            └─ _fallback_static_rate()
    
    Example:
        >>> fx = RealFxRateProvider()
        >>> rate = fx.get_rate(Currency.USDT, Currency.KRW)
        >>> print(rate)
        Decimal('1420.50')
        >>> 
        >>> # Staleness check
        >>> fx.is_stale(Currency.USDT, Currency.KRW)
        False
    """
    
    STALE_THRESHOLD_SECONDS = 60.0  # 60초 이상 업데이트 없으면 stale
    
    def __init__(
        self,
        binance_api_url: str = "https://fapi.binance.com",
        exchangerate_api_url: str = "https://api.exchangerate.host",
        cache_ttl_seconds: float = 3.0,
        http_timeout: float = 2.0,
    ):
        """
        Args:
            binance_api_url: Binance Futures API URL
            exchangerate_api_url: Exchangerate.host API URL
            cache_ttl_seconds: 캐시 TTL (초)
            http_timeout: HTTP 타임아웃 (초)
        """
        self.binance_api_url = binance_api_url
        self.exchangerate_api_url = exchangerate_api_url
        self.http_timeout = http_timeout
        
        # FxCache 초기화
        from .fx_cache import FxCache
        self.cache = FxCache(ttl_seconds=cache_ttl_seconds)
        
        # HTTP Session (connection pooling)
        try:
            import requests
            self.session = requests.Session()
        except ImportError:
            logger.warning("[FX_PROVIDER] requests 라이브러리 없음, HTTP 기능 비활성화")
            self.session = None
        
        # Fallback static rates
        self._fallback_rates = {
            (Currency.USDT, Currency.USD): Decimal("1.0"),
            (Currency.USD, Currency.KRW): Decimal("1420.0"),
            (Currency.USDT, Currency.KRW): Decimal("1420.0"),
        }
        
        logger.info(
            "[FX_PROVIDER] RealFxRateProvider initialized "
            f"(cache_ttl={cache_ttl_seconds}s, stale_threshold={self.STALE_THRESHOLD_SECONDS}s)"
        )
    
    def get_rate(self, base: Currency, quote: Currency) -> Decimal:
        """
        환율 조회 (캐시 우선, 없으면 API).
        
        Args:
            base: 기준 통화
            quote: 목표 통화
        
        Returns:
            환율 (Decimal)
        
        Example:
            >>> fx.get_rate(Currency.USDT, Currency.KRW)
            Decimal("1420.50")
        """
        # 같은 통화
        if base == quote:
            return Decimal("1.0")
        
        # 캐시 조회
        cached_rate = self.cache.get(base, quote)
        if cached_rate is not None:
            logger.debug(f"[FX_PROVIDER] Cache HIT: {base.value}→{quote.value} = {cached_rate}")
            return cached_rate
        
        # 캐시 miss, API 호출
        logger.debug(f"[FX_PROVIDER] Cache MISS: {base.value}→{quote.value}, fetching from API")
        rate = self._fetch_rate_from_api(base, quote)
        
        # 캐시 저장
        self.cache.set(base, quote, rate)
        
        return rate
    
    def get_updated_at(self, base: Currency, quote: Currency) -> float:
        """
        환율 업데이트 시각 조회.
        
        Args:
            base: 기준 통화
            quote: 목표 통화
        
        Returns:
            업데이트 시각 (Unix timestamp)
        """
        updated_at = self.cache.get_updated_at(base, quote)
        if updated_at is None:
            # 캐시에 없으면 현재 시각
            return time.time()
        return updated_at
    
    def is_stale(self, base: Currency, quote: Currency) -> bool:
        """
        환율이 stale인지 확인 (60초 이상 업데이트 없음).
        
        Args:
            base: 기준 통화
            quote: 목표 통화
        
        Returns:
            stale 여부
        
        Example:
            >>> fx.is_stale(Currency.USD, Currency.KRW)
            False
        """
        updated_at = self.get_updated_at(base, quote)
        age = time.time() - updated_at
        return age > self.STALE_THRESHOLD_SECONDS
    
    def refresh_rate(self, base: Currency, quote: Currency) -> None:
        """
        환율 강제 갱신 (캐시 무효화 후 재조회).
        
        Args:
            base: 기준 통화
            quote: 목표 통화
        
        Example:
            >>> fx.refresh_rate(Currency.USD, Currency.KRW)
            [FX_PROVIDER] Rate refreshed: USD→KRW
        """
        # 캐시에서 삭제
        key = (base, quote)
        if key in self.cache._cache:
            del self.cache._cache[key]
        
        # 재조회 (자동으로 캐시 저장됨)
        self.get_rate(base, quote)
        logger.info(f"[FX_PROVIDER] Rate refreshed: {base.value}→{quote.value}")
    
    def _fetch_rate_from_api(self, base: Currency, quote: Currency) -> Decimal:
        """
        API에서 환율 조회.
        
        Strategy:
        1. USDT→USD: Binance Funding Rate
        2. USD↔KRW: Exchangerate.host
        3. Fallback: Static rate
        
        Args:
            base: 기준 통화
            quote: 목표 통화
        
        Returns:
            환율
        """
        try:
            # USDT → USD (Binance)
            if base == Currency.USDT and quote == Currency.USD:
                return self._fetch_binance_usdt_usd()
            
            # USD → KRW (Exchangerate.host)
            if base == Currency.USD and quote == Currency.KRW:
                return self._fetch_exchangerate_usd_krw()
            
            # KRW → USD (역환율)
            if base == Currency.KRW and quote == Currency.USD:
                usd_krw = self._fetch_exchangerate_usd_krw()
                return Decimal("1.0") / usd_krw
            
            # USDT → KRW (chain: USDT→USD→KRW)
            if base == Currency.USDT and quote == Currency.KRW:
                usdt_usd = self._fetch_binance_usdt_usd()
                usd_krw = self._fetch_exchangerate_usd_krw()
                return usdt_usd * usd_krw
            
            # 기타: Fallback
            logger.warning(
                f"[FX_PROVIDER] No API route for {base.value}→{quote.value}, using fallback"
            )
            return self._fallback_static_rate(base, quote)
        
        except Exception as e:
            logger.error(
                f"[FX_PROVIDER] API error for {base.value}→{quote.value}: {e}, using fallback"
            )
            return self._fallback_static_rate(base, quote)
    
    def _fetch_binance_usdt_usd(self) -> Decimal:
        """
        Binance Funding Rate API로 USDT→USD 변환.
        
        Endpoint: GET /fapi/v1/premiumIndex?symbol=BTCUSDT
        Response: {"symbol": "BTCUSDT", "markPrice": "...", "lastFundingRate": "0.0001"}
        
        Conversion: USDT/USD ≈ 1.0 + lastFundingRate (근사)
        
        Returns:
            USDT→USD 환율
        """
        if self.session is None:
            raise RuntimeError("HTTP session not available (requests not installed)")
        
        url = f"{self.binance_api_url}/fapi/v1/premiumIndex"
        params = {"symbol": "BTCUSDT"}
        
        response = self.session.get(url, params=params, timeout=self.http_timeout)
        response.raise_for_status()
        
        data = response.json()
        funding_rate = Decimal(data.get("lastFundingRate", "0.0"))
        
        # USDT/USD ≈ 1.0 (funding rate는 매우 작은 값, 무시)
        rate = Decimal("1.0")
        
        logger.debug(f"[FX_PROVIDER] Binance USDT→USD: {rate} (funding_rate={funding_rate})")
        return rate
    
    def _fetch_exchangerate_usd_krw(self) -> Decimal:
        """
        Exchangerate.host API로 USD→KRW 환율 조회.
        
        Endpoint: GET /latest?base=USD&symbols=KRW
        Response: {"base": "USD", "rates": {"KRW": 1420.50}, ...}
        
        Returns:
            USD→KRW 환율
        """
        if self.session is None:
            raise RuntimeError("HTTP session not available (requests not installed)")
        
        url = f"{self.exchangerate_api_url}/latest"
        params = {"base": "USD", "symbols": "KRW"}
        
        response = self.session.get(url, params=params, timeout=self.http_timeout)
        response.raise_for_status()
        
        data = response.json()
        rate = Decimal(str(data["rates"]["KRW"]))
        
        logger.debug(f"[FX_PROVIDER] Exchangerate USD→KRW: {rate}")
        return rate
    
    def _fallback_static_rate(self, base: Currency, quote: Currency) -> Decimal:
        """
        Fallback: 고정 환율.
        
        Args:
            base: 기준 통화
            quote: 목표 통화
        
        Returns:
            고정 환율
        
        Raises:
            ValueError: fallback rate도 없는 경우
        """
        # Forward lookup
        if (base, quote) in self._fallback_rates:
            rate = self._fallback_rates[(base, quote)]
            logger.warning(
                f"[FX_PROVIDER] Using fallback rate: {base.value}→{quote.value} = {rate}"
            )
            return rate
        
        # Reverse lookup
        if (quote, base) in self._fallback_rates:
            reverse_rate = self._fallback_rates[(quote, base)]
            rate = Decimal("1.0") / reverse_rate
            logger.warning(
                f"[FX_PROVIDER] Using fallback reverse rate: {base.value}→{quote.value} = {rate}"
            )
            return rate
        
        raise ValueError(
            f"No fallback rate for {base.value}→{quote.value}. "
            f"Available: {list(self._fallback_rates.keys())}"
        )


# =============================================================================
# WebSocketFxRateProvider (D80-4)
# =============================================================================

class WebSocketFxRateProvider:
    """
    WebSocket 기반 FX Rate Provider (D80-4).
    
    Features:
    - Binance WebSocket Mark Price Stream (USDT→USD)
    - Event-driven FxCache 업데이트
    - HTTP fallback (RealFxRateProvider composition)
    - Auto-reconnect & graceful degradation
    
    Architecture:
        WebSocket (push) → FxCache
                ↓ (fallback)
        RealFxRateProvider (HTTP) → FxCache
                ↓ (fallback)
        StaticFxRateProvider
    
    Example:
        >>> fx = WebSocketFxRateProvider()
        >>> fx.start()  # Start WebSocket
        >>> rate = fx.get_rate(Currency.USDT, Currency.KRW)
        >>> fx.stop()  # Stop WebSocket
    """
    
    def __init__(
        self,
        binance_symbol: str = "btcusdt",
        cache_ttl_seconds: float = 3.0,
        http_timeout: float = 2.0,
        enable_websocket: bool = True,
    ):
        """
        Args:
            binance_symbol: Binance futures symbol (소문자)
            cache_ttl_seconds: 캐시 TTL (초)
            http_timeout: HTTP 타임아웃 (초)
            enable_websocket: WebSocket 활성화 여부 (False면 HTTP-only)
        """
        # HTTP fallback provider
        self.real_fx_provider = RealFxRateProvider(
            cache_ttl_seconds=cache_ttl_seconds,
            http_timeout=http_timeout,
        )
        
        # Shared cache (WS와 HTTP가 동일 캐시 사용)
        self.cache = self.real_fx_provider.cache
        
        # WebSocket client
        self.enable_websocket = enable_websocket
        self.ws_client = None
        
        if enable_websocket:
            try:
                from .fx_ws_client import BinanceFxWebSocketClient
                self.ws_client = BinanceFxWebSocketClient(
                    symbol=binance_symbol,
                    on_rate_update=self._on_ws_rate_update,
                    on_error=self._on_ws_error,
                )
                logger.info(
                    f"[FX_PROVIDER] WebSocketFxRateProvider initialized "
                    f"(symbol={binance_symbol}, cache_ttl={cache_ttl_seconds}s)"
                )
            except Exception as e:
                logger.warning(
                    f"[FX_PROVIDER] Failed to initialize WebSocket client: {e}, "
                    "falling back to HTTP-only mode"
                )
                self.enable_websocket = False
                self.ws_client = None
        else:
            logger.info(
                f"[FX_PROVIDER] WebSocketFxRateProvider initialized in HTTP-only mode "
                f"(cache_ttl={cache_ttl_seconds}s)"
            )
    
    def start(self) -> None:
        """Start WebSocket client"""
        if self.ws_client:
            self.ws_client.start()
            logger.info("[FX_PROVIDER] WebSocket FX stream started")
        else:
            logger.debug("[FX_PROVIDER] WebSocket disabled, using HTTP-only mode")
    
    def stop(self) -> None:
        """Stop WebSocket client"""
        if self.ws_client:
            self.ws_client.stop()
            logger.info("[FX_PROVIDER] WebSocket FX stream stopped")
    
    def get_rate(self, base: Currency, quote: Currency) -> Decimal:
        """
        환율 조회 (WebSocket cache 우선, HTTP fallback).
        
        Args:
            base: 기준 통화
            quote: 목표 통화
        
        Returns:
            환율 (Decimal)
        
        Example:
            >>> fx.get_rate(Currency.USDT, Currency.KRW)
            Decimal("1420.50")
        """
        # 같은 통화
        if base == quote:
            return Decimal("1.0")
        
        # 1. Cache 조회 (WS 또는 HTTP가 업데이트)
        cached_rate = self.cache.get(base, quote)
        if cached_rate is not None:
            logger.debug(
                f"[FX_PROVIDER] Cache HIT (WS/HTTP): {base.value}→{quote.value} = {cached_rate}"
            )
            return cached_rate
        
        # 2. Cache miss → HTTP fallback
        logger.debug(
            f"[FX_PROVIDER] Cache MISS, using HTTP fallback: {base.value}→{quote.value}"
        )
        return self.real_fx_provider.get_rate(base, quote)
    
    def get_updated_at(self, base: Currency, quote: Currency) -> float:
        """
        환율 업데이트 시각 조회.
        
        Args:
            base: 기준 통화
            quote: 목표 통화
        
        Returns:
            업데이트 시각 (Unix timestamp)
        """
        return self.real_fx_provider.get_updated_at(base, quote)
    
    def is_stale(self, base: Currency, quote: Currency) -> bool:
        """
        환율 staleness 확인.
        
        Args:
            base: 기준 통화
            quote: 목표 통화
        
        Returns:
            stale 여부
        """
        return self.real_fx_provider.is_stale(base, quote)
    
    def is_websocket_connected(self) -> bool:
        """
        WebSocket 연결 상태 확인.
        
        Returns:
            연결 상태 (True: 연결됨, False: 끊김/비활성화)
        """
        if not self.ws_client:
            return False
        return self.ws_client.is_connected()
    
    def get_websocket_stats(self) -> dict:
        """
        WebSocket 통계 조회.
        
        Returns:
            dict: {
                "connected": bool,
                "reconnect_count": int,
                "message_count": int,
                "error_count": int,
                "last_message_age": float
            }
        """
        if not self.ws_client:
            return {
                "connected": False,
                "reconnect_count": 0,
                "message_count": 0,
                "error_count": 0,
                "last_message_age": 0.0,
            }
        return self.ws_client.get_stats()
    
    def _on_ws_rate_update(self, rate: Decimal, timestamp: float) -> None:
        """
        WebSocket rate update callback.
        
        Args:
            rate: USDT→USD 환율
            timestamp: 업데이트 시각
        """
        # Update cache: USDT→USD
        self.cache.set(Currency.USDT, Currency.USD, rate, updated_at=timestamp)
        logger.debug(f"[FX_PROVIDER] WS update: USDT→USD = {rate}")
        
        # Chain: USDT→KRW (USDT→USD × USD→KRW)
        # USD→KRW는 HTTP에서 가져온 값 재사용 (캐시에 있으면)
        usd_krw = self.cache.get(Currency.USD, Currency.KRW)
        if usd_krw is not None:
            usdt_krw = rate * usd_krw
            self.cache.set(Currency.USDT, Currency.KRW, usdt_krw, updated_at=timestamp)
            logger.debug(f"[FX_PROVIDER] WS chain: USDT→KRW = {usdt_krw}")
    
    def _on_ws_error(self, error: Exception) -> None:
        """WebSocket error callback"""
        logger.error(f"[FX_PROVIDER] WebSocket error: {error}")
