# D80-0: Multi-Currency Support - Domain & Interface Design

**Status:** 🚧 **IN PROGRESS**  
**Date:** 2025-12-01  
**Owner:** Arbitrage Bot Team

---

## 📋 Overview

Cross-Exchange 아비트라지 시스템의 **Multi-Currency Support** 설계 및 구현.

### 목표
- **Currency-aware Architecture**: 모든 PnL/Risk/Metrics가 통화를 명시적으로 인식
- **Future-proof Design**: KRW뿐만 아니라 USD/USDT/BTC 등 다양한 Base Currency 지원
- **Backward Compatibility**: 기존 KRW 기반 코드 100% 호환 유지
- **Production-grade**: "1조 이상 버는 초상용급" 시스템 기준 적용

### 배경
현재 시스템(D79-6까지)은 **KRW 기준이 암묵적으로 가정**되어 있음:
- `CrossExchangePnLTracker`: `_daily_pnl_krw` 변수명에 KRW 하드코딩
- `CrossExchangeMetrics`: `cross_daily_pnl_krw`, `cross_unrealized_pnl_krw` 메트릭 이름
- Upbit KRW 마켓 ↔ Binance USDT 마켓 구조 암묵적 가정

**문제점:**
- 향후 Upbit BTC 마켓, Binance USD 마켓 등 확장 시 코드 대규모 수정 필요
- 서로 다른 통화의 PnL/Exposure를 직접 더하면 잘못된 계산 발생
- 환율 변환 로직이 산재되어 일관성 보장 어려움

---

## 🎯 Requirements

### 1. Functional Requirements

#### 1.1 다양한 Base Currency 지원
```python
# 지원할 Base Currency 목록
- KRW (Upbit 기준통화)
- USD (Global standard, Binance USD 마켓)
- USDT (Stablecoin, Binance USDT 마켓 기준)
- BTC (Crypto standard, BTC 마켓)
```

#### 1.2 Currency-aware Money Operations
```python
# ✅ 같은 통화끼리만 연산 허용
Money(1000, KRW) + Money(500, KRW) = Money(1500, KRW)

# ❌ 다른 통화 직접 연산 금지
Money(1000, KRW) + Money(1, USD)  # TypeError 발생

# ✅ 변환 후 연산
fx = FxRateProvider()
usd_in_krw = Money(1, USD).convert_to(KRW, fx)
Money(1000, KRW) + usd_in_krw  # OK
```

#### 1.3 Cross-Exchange PnL 통합 집계
```python
# Upbit KRW 마켓: +50,000 KRW 수익
# Binance USDT 마켓: -30 USDT 손실

# Base Currency = KRW로 통합 집계
total_pnl_krw = 50_000 + (-30 * 1500) = 5,000 KRW
```

#### 1.4 RiskGuard Currency-aware Exposure
```python
# KRW 기준 Exposure/Imbalance 계산
upbit_krw = Money(10_000_000, KRW)
binance_usdt = Money(7000, USDT)

# USDT → KRW 변환 후 Exposure 계산
binance_krw = binance_usdt.convert_to(KRW, fx)
total_krw = upbit_krw + binance_krw
exposure_ratio = upbit_krw / total_krw
```

#### 1.5 Metrics with Currency Dimension
```python
# ✅ Base Currency를 명시적으로 기록
cross_daily_pnl{base_currency="KRW", symbol="KRW-BTC"} = 50000.0
cross_daily_pnl{base_currency="USD", symbol="KRW-BTC"} = 35.2

# ✅ Local Currency도 함께 기록 (선택적)
cross_daily_pnl_local{currency="KRW", symbol="KRW-BTC"} = 50000.0
cross_daily_pnl_local{currency="USDT", symbol="USDT-BTC"} = -30.0
```

---

### 2. Non-Functional Requirements

#### 2.1 Performance
- **Currency 변환 latency < 1ms** (캐싱 활용)
- **Money 객체 생성/연산 overhead < 10μs**
- **메모리 효율**: Money 객체 크기 ≤ 32 bytes

#### 2.2 Accuracy
- **환율 정확도**: 소수점 4자리 이상 (예: 1 USD = 1420.5000 KRW)
- **PnL 계산 정확도**: Decimal 사용 (float 부동소수점 오차 제거)
- **Rounding 규칙**: 통화별 Round-to-even (Banker's rounding)

#### 2.3 Reliability
- **FxRateProvider 장애 격리**: FX 레이트 조회 실패 시 fallback 레이트 사용
- **Stale Rate 감지**: 환율 업데이트 시간 추적, 오래된 레이트 경고
- **Type Safety**: Currency/Money 타입 체크 100% (mypy strict mode)

#### 2.4 Backward Compatibility
- **기존 코드 100% 동작 유지**: Currency를 명시하지 않으면 KRW 기본값
- **Gradual Migration**: 단계별 Currency-aware 전환 가능
- **Test Coverage**: 기존 72 tests 모두 PASS 유지

---

## 🏗️ Domain Model

### 1. Currency Enum

```python
from enum import Enum

class Currency(str, Enum):
    """
    지원 통화 목록.
    
    str Enum을 사용하여 JSON serialization, Prometheus label 호환성 확보.
    """
    KRW = "KRW"  # 원화 (Upbit 기준통화)
    USD = "USD"  # 달러 (Global standard)
    USDT = "USDT"  # 테더 (Stablecoin)
    BTC = "BTC"  # 비트코인 (Crypto standard)
    ETH = "ETH"  # 이더리움 (향후 확장)
    
    @property
    def decimal_places(self) -> int:
        """통화별 소수점 자릿수"""
        return {
            Currency.KRW: 0,   # 원화는 정수
            Currency.USD: 2,   # 센트 단위
            Currency.USDT: 2,  # 센트 단위
            Currency.BTC: 8,   # 사토시 단위
            Currency.ETH: 6,   # Wei 단위 (간소화)
        }[self]
    
    @property
    def symbol(self) -> str:
        """통화 기호"""
        return {
            Currency.KRW: "₩",
            Currency.USD: "$",
            Currency.USDT: "₮",
            Currency.BTC: "₿",
            Currency.ETH: "Ξ",
        }[self]
```

---

### 2. Money Class

```python
from dataclasses import dataclass
from decimal import Decimal
from typing import Union

@dataclass(frozen=True)
class Money:
    """
    금액 + 통화를 함께 표현하는 Value Object.
    
    Immutable, Type-safe, Currency-aware 연산 지원.
    """
    amount: Decimal
    currency: Currency
    
    def __post_init__(self):
        """Validation: amount는 Decimal, currency는 Currency Enum"""
        if not isinstance(self.amount, Decimal):
            # Auto-convert to Decimal
            object.__setattr__(self, 'amount', Decimal(str(self.amount)))
        
        if not isinstance(self.currency, Currency):
            raise TypeError(f"currency must be Currency Enum, got {type(self.currency)}")
    
    # ========================================================================
    # Arithmetic Operations (같은 통화끼리만)
    # ========================================================================
    
    def __add__(self, other: 'Money') -> 'Money':
        """덧셈 (같은 통화만 허용)"""
        if not isinstance(other, Money):
            raise TypeError(f"Cannot add Money with {type(other)}")
        
        if self.currency != other.currency:
            raise ValueError(
                f"Cannot add different currencies: {self.currency} + {other.currency}. "
                "Use convert_to() first."
            )
        
        return Money(self.amount + other.amount, self.currency)
    
    def __sub__(self, other: 'Money') -> 'Money':
        """뺄셈 (같은 통화만 허용)"""
        if not isinstance(other, Money):
            raise TypeError(f"Cannot subtract {type(other)} from Money")
        
        if self.currency != other.currency:
            raise ValueError(
                f"Cannot subtract different currencies: {self.currency} - {other.currency}. "
                "Use convert_to() first."
            )
        
        return Money(self.amount - other.amount, self.currency)
    
    def __mul__(self, scalar: Union[int, float, Decimal]) -> 'Money':
        """스칼라 곱셈"""
        if isinstance(scalar, (int, float)):
            scalar = Decimal(str(scalar))
        
        return Money(self.amount * scalar, self.currency)
    
    def __truediv__(self, scalar: Union[int, float, Decimal]) -> 'Money':
        """스칼라 나눗셈"""
        if isinstance(scalar, (int, float)):
            scalar = Decimal(str(scalar))
        
        if scalar == 0:
            raise ZeroDivisionError("Cannot divide Money by zero")
        
        return Money(self.amount / scalar, self.currency)
    
    # ========================================================================
    # Comparison (같은 통화끼리만)
    # ========================================================================
    
    def __lt__(self, other: 'Money') -> bool:
        if self.currency != other.currency:
            raise ValueError(f"Cannot compare different currencies: {self.currency} vs {other.currency}")
        return self.amount < other.amount
    
    def __le__(self, other: 'Money') -> bool:
        if self.currency != other.currency:
            raise ValueError(f"Cannot compare different currencies: {self.currency} vs {other.currency}")
        return self.amount <= other.amount
    
    def __gt__(self, other: 'Money') -> bool:
        if self.currency != other.currency:
            raise ValueError(f"Cannot compare different currencies: {self.currency} vs {other.currency}")
        return self.amount > other.amount
    
    def __ge__(self, other: 'Money') -> bool:
        if self.currency != other.currency:
            raise ValueError(f"Cannot compare different currencies: {self.currency} vs {other.currency}")
        return self.amount >= other.amount
    
    # ========================================================================
    # Conversion & Formatting
    # ========================================================================
    
    def convert_to(self, target_currency: Currency, fx_provider: 'FxRateProvider') -> 'Money':
        """
        다른 통화로 변환.
        
        Args:
            target_currency: 목표 통화
            fx_provider: 환율 제공자
        
        Returns:
            변환된 Money 객체
        """
        if self.currency == target_currency:
            return self  # 같은 통화면 그대로 반환
        
        rate = fx_provider.get_rate(self.currency, target_currency)
        converted_amount = self.amount * rate
        
        return Money(converted_amount, target_currency)
    
    def round(self) -> 'Money':
        """통화별 소수점 자릿수로 반올림"""
        places = self.currency.decimal_places
        quantize_str = "1" if places == 0 else f"0.{'0' * places}"
        rounded_amount = self.amount.quantize(Decimal(quantize_str))
        
        return Money(rounded_amount, self.currency)
    
    def __str__(self) -> str:
        """사람이 읽기 쉬운 형식"""
        return f"{self.currency.symbol}{self.amount:,.{self.currency.decimal_places}f}"
    
    def __repr__(self) -> str:
        """개발자용 표현"""
        return f"Money({self.amount}, {self.currency.value})"
    
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
```

---

### 3. FxRateProvider Interface

```python
from abc import ABC, abstractmethod
from typing import Protocol

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
            get_rate(Currency.USD, Currency.KRW) = Decimal("1420.50")
            → 1 USD = 1420.50 KRW
        """
        ...
    
    def get_updated_at(self, base: Currency, quote: Currency) -> float:
        """
        환율 업데이트 시각 (Unix timestamp).
        
        Returns:
            timestamp (초 단위)
        """
        ...
```

---

### 4. StaticFxRateProvider (테스트/개발용)

```python
import time
from typing import Dict, Tuple

class StaticFxRateProvider:
    """
    정적 환율 제공자 (테스트/개발용).
    
    고정된 환율 테이블을 메모리에 저장.
    """
    
    def __init__(self, rates: Dict[Tuple[Currency, Currency], Decimal]):
        """
        Args:
            rates: {(base, quote): rate} 형식의 환율 테이블
        
        Example:
            rates = {
                (Currency.USD, Currency.KRW): Decimal("1420.50"),
                (Currency.USDT, Currency.KRW): Decimal("1500.00"),
            }
        """
        self.rates = rates
        self.updated_at = time.time()
    
    def get_rate(self, base: Currency, quote: Currency) -> Decimal:
        """환율 조회"""
        if base == quote:
            return Decimal("1.0")
        
        # Forward lookup
        if (base, quote) in self.rates:
            return self.rates[(base, quote)]
        
        # Reverse lookup (역환율)
        if (quote, base) in self.rates:
            return Decimal("1.0") / self.rates[(quote, base)]
        
        # Triangulation (향후 확장: USD를 중개 통화로 사용)
        # 예: KRW → BTC = (KRW → USD) * (USD → BTC)
        
        raise ValueError(f"No FX rate found for {base} → {quote}")
    
    def get_updated_at(self, base: Currency, quote: Currency) -> float:
        """업데이트 시각"""
        return self.updated_at
```

---

## 🔄 Integration Points

### 1. CrossExchangePnLTracker 통합

**AS-IS (KRW 하드코딩):**
```python
class CrossExchangePnLTracker:
    def __init__(self):
        self._daily_pnl_krw: float = 0.0  # ❌ KRW 하드코딩
    
    def add_trade(self, pnl_krw: float):
        self._daily_pnl_krw += pnl_krw
```

**TO-BE (Currency-aware):**
```python
class CrossExchangePnLTracker:
    def __init__(self, base_currency: Currency = Currency.KRW):
        self.base_currency = base_currency
        self._daily_pnl: Money = Money(Decimal("0"), base_currency)
    
    def add_trade(self, pnl: Money, fx_provider: FxRateProvider):
        # Base currency로 변환 후 누적
        pnl_in_base = pnl.convert_to(self.base_currency, fx_provider)
        self._daily_pnl += pnl_in_base
```

---

### 2. CrossExchangeRiskGuard 통합

**Exposure 계산 Currency-aware:**
```python
def _check_cross_sync_rules(self, decision: CrossExchangeDecision) -> CrossRiskDecision:
    # Upbit / Binance 잔고를 Base Currency로 변환
    upbit_balance_local = Money(upbit_balance, Currency.KRW)
    binance_balance_local = Money(binance_balance, Currency.USDT)
    
    # Base Currency (예: KRW)로 통합
    upbit_balance_base = upbit_balance_local.convert_to(self.base_currency, self.fx_provider)
    binance_balance_base = binance_balance_local.convert_to(self.base_currency, self.fx_provider)
    
    total_balance = upbit_balance_base + binance_balance_base
    exposure_ratio = upbit_balance_base / total_balance
```

---

### 3. CrossExchangeMetrics 통합

**Metric 이름 Currency Dimension 추가:**

**AS-IS:**
```python
# ❌ KRW 하드코딩
cross_daily_pnl_krw{symbol="KRW-BTC"} = 50000.0
```

**TO-BE:**
```python
# ✅ Base Currency 명시
cross_daily_pnl{base_currency="KRW", symbol="KRW-BTC"} = 50000.0
cross_daily_pnl{base_currency="USD", symbol="KRW-BTC"} = 35.2

# ✅ Local Currency도 기록 (선택적)
cross_daily_pnl_local{currency="KRW", symbol="KRW-BTC"} = 50000.0
cross_daily_pnl_local{currency="USDT", symbol="USDT-BTC"} = -30.0
```

**메트릭 수집 코드:**
```python
def record_pnl_snapshot(self, snapshot: CrossExchangePnLSnapshot):
    # Base Currency PnL
    self.backend.set_gauge(
        "cross_daily_pnl",
        value=float(snapshot.daily_pnl.amount),
        labels={
            "base_currency": snapshot.daily_pnl.currency.value,
            "symbol": snapshot.symbol,
        }
    )
    
    # Local Currency PnL (선택적)
    for local_pnl in snapshot.local_pnls:
        self.backend.set_gauge(
            "cross_daily_pnl_local",
            value=float(local_pnl.amount),
            labels={
                "currency": local_pnl.currency.value,
                "symbol": snapshot.symbol,
            }
        )
```

---

### 4. CrossExchangeExecutor 통합

**주문 금액 Currency-aware:**
```python
def execute_decision(self, decision: CrossExchangeDecision):
    # Upbit: KRW 마켓
    upbit_order_amount_krw = Money(
        Decimal(str(decision.upbit_notional_krw)),
        Currency.KRW
    )
    
    # Binance: USDT 마켓 (KRW → USDT 변환)
    binance_order_amount_usdt = upbit_order_amount_krw.convert_to(
        Currency.USDT,
        self.fx_provider
    )
```

---

## 📐 Architecture & Data Flow

### 1. Layering

```
┌─────────────────────────────────────────────────────────────┐
│  UI / Monitoring (Grafana, Prometheus)                      │
│  - Base Currency + Local Currency 둘 다 관측                 │
└─────────────────────────────────────────────────────────────┘
                           ↑
┌─────────────────────────────────────────────────────────────┐
│  Domain Layer (Business Logic)                              │
│  - PnL / Exposure / Risk: Base Currency 기준                │
│  - Money 객체 사용, Currency 명시적                           │
└─────────────────────────────────────────────────────────────┘
                           ↑
┌─────────────────────────────────────────────────────────────┐
│  Input Layer (Exchange Adapter, Universe)                   │
│  - Upbit: KRW 마켓 가격/잔고                                  │
│  - Binance: USDT/USD 마켓 가격/잔고                           │
│  - Local Currency로 Money 객체 생성                           │
└─────────────────────────────────────────────────────────────┘
```

### 2. Currency Conversion Flow

```
                    ┌──────────────┐
                    │  FxProvider  │
                    └──────────────┘
                           ↑
                           │ get_rate()
                           │
    ┌──────────────────────┴──────────────────────┐
    │                                              │
┌───▼───────┐                              ┌──────▼──────┐
│ Upbit KRW │                              │ Binance USD │
│  Balance  │                              │   Balance   │
└───────────┘                              └─────────────┘
    │                                              │
    │ Money(10M, KRW)                             │ Money(7K, USDT)
    │                                              │
    └──────────────────┬───────────────────────────┘
                       │
                       │ convert_to(base_currency)
                       │
                  ┌────▼─────┐
                  │   PnL    │
                  │ Tracker  │
                  │  (Base)  │
                  └──────────┘
```

---

## 🗺️ Migration Plan

### Phase 1: D80-0 (현재) - Domain & Interface Design ✅
- ✅ Currency Enum, Money, FxRateProvider 정의
- ✅ StaticFxRateProvider 구현 (테스트용)
- ✅ 설계 문서 작성
- ✅ 샘플 단위 테스트 (5~10개)
- **Impact**: None (기존 코드 변경 없음, 새 모듈만 추가)

### Phase 2: D80-1 - Core Layer Refactoring
- 🔲 CrossExchangePnLTracker → Money 기반으로 리팩토링
- 🔲 CrossExchangeRiskGuard → Currency-aware Exposure/Imbalance
- 🔲 CrossExchangeMetrics → Base Currency dimension 추가
- 🔲 기존 테스트 60/60 유지 + 신규 Currency 테스트 10+
- **Impact**: Medium (내부 구현 변경, public interface 일부 확장)

### Phase 3: D80-2 - Exchange Adapter & Universe Integration
- 🔲 Universe에 Currency 메타데이터 추가
- 🔲 Exchange Adapter에서 Local Currency Money 생성
- 🔲 CrossExchangeExecutor → Currency-aware 주문 금액 계산
- 🔲 기존 테스트 72/72 유지 + 신규 Multi-currency 테스트 15+
- **Impact**: Medium-High (Exchange 연동 부분 수정)

### Phase 4: D80-3 - Real FX Rate Provider
- 🔲 Binance FX API 연동 (USDT/USD → KRW)
- 🔲 외부 환율 API 연동 (USD → KRW, fallback)
- 🔲 FX Rate 캐싱 + Staleness 감지
- 🔲 FX Rate 변동에 대한 Alert/Metric
- **Impact**: High (외부 API 의존성 추가)

---

## ⚠️ Risks & Mitigations

### Risk 1: FX Rate 조회 latency 증가
- **Mitigation**: 
  - 환율 캐싱 (TTL 10초)
  - Async prefetch (주기적으로 미리 조회)
  - Fallback to static rate (장애 시)

### Risk 2: Decimal 연산 성능 오버헤드
- **Mitigation**:
  - Money 객체를 필요한 지점에만 사용
  - 내부 계산은 Decimal 유지, 최종 출력만 Money
  - 벤치마크: Decimal vs float 성능 비교 (목표: < 10% 오버헤드)

### Risk 3: Backward Compatibility 깨짐
- **Mitigation**:
  - 기본값으로 KRW 사용 (명시하지 않으면 KRW)
  - 기존 테스트 100% PASS 유지
  - Deprecation 경고 (2 releases 후 제거)

### Risk 4: FX Rate 정확도 문제
- **Mitigation**:
  - 다중 소스 사용 (Binance, Upbit, 외부 API)
  - Outlier 감지 (3σ 벗어나면 경고)
  - Manual override 가능 (운영 중 긴급 조정)

---

## 🧪 Testing Strategy

### 1. Unit Tests (D80-0)
- Currency Enum 생성/속성
- Money 객체 생성/연산
- Money 같은 통화 연산 성공
- Money 다른 통화 연산 실패
- Money convert_to() 정확도
- StaticFxRateProvider 환율 조회
- FX Rate 역환율 계산

### 2. Integration Tests (D80-1)
- PnLTracker with Multi-currency trades
- RiskGuard Exposure calculation with FX conversion
- Metrics with base_currency dimension

### 3. End-to-End Tests (D80-2)
- Full trade cycle: Entry(KRW) → Exit(USDT) → PnL(KRW)
- Multi-symbol with different base currencies

### 4. Regression Tests
- 모든 기존 D79 테스트 72/72 PASS 유지

---

## 📚 Open Questions

### Q1: Base Currency를 Settings에서 변경 가능하게?
**답**: ✅ Yes
- `Settings.BASE_CURRENCY = Currency.KRW` (기본값)
- `.env`에서 `BASE_CURRENCY=USD` 설정 가능
- 단, 운영 중 변경은 금지 (PnL 누적값 오염 방지)

### Q2: 심볼별로 다른 Base Currency 사용 가능?
**답**: ⏳ Future (D80-4+)
- 현재(D80-0~3): 프로젝트 전체 단일 Base Currency
- 향후: 심볼별 Base Currency 설정 가능 (복잡도 증가)

### Q3: BTC/ETH 같은 Crypto를 Base Currency로?
**답**: ✅ Yes (설계상 지원)
- Currency Enum에 이미 포함
- FX Rate: BTC → KRW, BTC → USD 등
- 단, 변동성 큼 → PnL 해석 주의 필요

### Q4: FX Rate 업데이트 주기는?
**답**: 
- D80-0~2: Static (테스트용)
- D80-3: 10초 (캐싱 TTL)
- D80-4+: 실시간 (WebSocket FX stream)

---

## 📦 Deliverables (D80-0)

1. ✅ `docs/D80_0_MULTI_CURRENCY_SUPPORT_DESIGN.md` (이 문서)
2. ⏳ `arbitrage/common/currency.py` (Currency, Money, FxRateProvider)
3. ⏳ `tests/test_d80_0_currency_domain.py` (단위 테스트 5~10개)
4. ⏳ `D_ROADMAP.md` 업데이트 (D80-0 완료 상태)
5. ⏳ Git commit: `[D80-0] Multi-Currency Support - Domain & Interface Design`

---

## 🎓 References

- [ISO 4217: Currency Codes](https://en.wikipedia.org/wiki/ISO_4217)
- [Martin Fowler: Money Pattern](https://martinfowler.com/eaaCatalog/money.html)
- [Python Decimal: Exact Decimal Arithmetic](https://docs.python.org/3/library/decimal.html)
- D79-5: Cross-Exchange RiskGuard (PnL tracking baseline)
- D79-6: Cross-Exchange Monitoring (Metrics baseline)

---

**End of Document**
