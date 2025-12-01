# D80-1: Multi-Currency Core Layer Integration

**Status:** 🚧 **IN PROGRESS**  
**Date:** 2025-12-01  
**Owner:** Arbitrage Bot Team

---

## 📋 Overview

D80-0에서 정의한 Multi-Currency Domain Model (Currency, Money, FxRateProvider)을  
Core Layer 컴포넌트들에 통합.

### 목표
- **CrossExchangePnLTracker**: float → Money 타입 전환
- **CrossExchangeRiskGuard**: Currency-aware Exposure/Imbalance 계산
- **CrossExchangeMetrics**: base_currency dimension 추가
- **Backward Compatibility**: 기존 D79 테스트 72/72 유지

### 배경
D80-0 완료 후, 실제 Core Layer가 여전히 KRW를 암묵적으로 가정:
- `CrossExchangePnLTracker`: `_daily_pnl_krw: float`
- `CrossExchangeRiskGuardConfig`: `max_daily_loss_krw: float`
- `CrossExchangePnLSnapshot`: `daily_pnl_krw: float`, `unrealized_pnl_krw: float`
- `CrossExchangeMetrics`: 메트릭 이름에 `_krw` suffix

**문제점:**
- USD/USDT/BTC 기준 PnL 지원 불가
- 다중 통화 잔고 집계 시 직접 덧셈 → 오류
- 메트릭에 Base Currency 정보 없음

---

## 🎯 Requirements

### 1. Functional Requirements

#### 1.1 CrossExchangePnLTracker Money 기반 리팩토링
```python
# AS-IS (KRW 하드코딩)
class CrossExchangePnLTracker:
    def __init__(self):
        self._daily_pnl_krw: float = 0.0
    
    def add_trade(self, pnl_krw: float):
        self._daily_pnl_krw += pnl_krw

# TO-BE (Currency-aware)
class CrossExchangePnLTracker:
    def __init__(self, base_currency: Currency = Currency.KRW, fx_provider: Optional[FxRateProvider] = None):
        self.base_currency = base_currency
        self.fx_provider = fx_provider or StaticFxRateProvider({})
        self._daily_pnl: Money = Money(Decimal("0"), base_currency)
    
    def add_trade(self, pnl: Union[Money, float], currency: Optional[Currency] = None):
        # float + currency → Money 변환 (Backward compatibility)
        if isinstance(pnl, (int, float)):
            if currency is None:
                currency = Currency.KRW  # Default
            pnl = Money(Decimal(str(pnl)), currency)
        
        # Base currency로 변환 후 누적
        pnl_in_base = pnl.convert_to(self.base_currency, self.fx_provider)
        self._daily_pnl += pnl_in_base
```

#### 1.2 RiskGuard Config Currency-aware
```python
# AS-IS
@dataclass
class CrossExchangeRiskGuardConfig:
    max_daily_loss_krw: float = 5_000_000.0

# TO-BE
@dataclass
class CrossExchangeRiskGuardConfig:
    max_daily_loss: Money = field(default_factory=lambda: Money(Decimal("5000000"), Currency.KRW))
    base_currency: Currency = Currency.KRW
```

#### 1.3 Metrics base_currency dimension
```python
# AS-IS
cross_daily_pnl_krw{symbol="KRW-BTC"} = 50000.0

# TO-BE
cross_daily_pnl{base_currency="KRW", symbol="KRW-BTC"} = 50000.0
cross_daily_pnl{base_currency="USD", symbol="KRW-BTC"} = 35.2
```

#### 1.4 CrossExchangePnLSnapshot Money 기반
```python
# AS-IS
@dataclass
class CrossExchangePnLSnapshot:
    daily_pnl_krw: float
    unrealized_pnl_krw: float = 0.0

# TO-BE
@dataclass
class CrossExchangePnLSnapshot:
    daily_pnl: Money
    unrealized_pnl: Optional[Money] = None
    base_currency: Currency = Currency.KRW  # 명시적
```

---

### 2. Non-Functional Requirements

#### 2.1 Backward Compatibility (100%)
- **기존 D79 테스트 72/72 유지 필수**
- float로 PnL 전달 시 자동으로 KRW Money로 변환
- 기존 메트릭 이름 유지 (deprecated, 새 이름 병행 사용)

#### 2.2 Performance
- Money 객체 생성/변환 overhead < 10%
- FX Rate 조회 캐싱 활용

#### 2.3 Type Safety
- Money vs float 혼용 시 명확한 에러 메시지
- Currency mismatch 시 ValueError 발생

---

## 🏗️ Implementation Plan

### Phase 1: PnLTracker 리팩토링

#### 변경 파일: `arbitrage/cross_exchange/risk_guard.py`

**CrossExchangePnLTracker 리팩토링:**

```python
from decimal import Decimal
from typing import Union, Optional
from arbitrage.common.currency import Currency, Money, FxRateProvider, StaticFxRateProvider


class CrossExchangePnLTracker:
    """
    Cross-Exchange PnL 추적기 (Multi-Currency 지원).
    
    Daily PnL 및 Consecutive loss 추적.
    Base Currency 기준으로 모든 PnL을 통합 집계.
    """
    
    def __init__(
        self,
        base_currency: Currency = Currency.KRW,
        fx_provider: Optional[FxRateProvider] = None,
    ):
        """
        Args:
            base_currency: 기준 통화 (기본: KRW)
            fx_provider: 환율 제공자 (None 시 기본 StaticFxRateProvider)
        """
        self.base_currency = base_currency
        self.fx_provider = fx_provider or StaticFxRateProvider({
            # Fallback rates (테스트/개발용)
            (Currency.USD, Currency.KRW): Decimal("1420.50"),
            (Currency.USDT, Currency.KRW): Decimal("1500.00"),
        })
        
        self._daily_pnl: Money = Money(Decimal("0"), base_currency)
        self._daily_pnl_reset_time: float = 0.0
        self._consecutive_loss_count: int = 0
        self._last_trade_pnl: Money = Money(Decimal("0"), base_currency)
    
    def add_trade(
        self,
        pnl: Union[Money, float],
        currency: Optional[Currency] = None,
    ) -> None:
        """
        거래 PnL 추가 (Backward compatible).
        
        Args:
            pnl: 거래 손익 (Money 또는 float)
            currency: pnl이 float인 경우 통화 (기본: KRW)
        
        Example:
            # 새 방식 (Money)
            tracker.add_trade(Money(Decimal("50000"), Currency.KRW))
            
            # 기존 방식 (float, 자동 KRW 변환)
            tracker.add_trade(50000.0)
            tracker.add_trade(50000.0, Currency.KRW)
        """
        # float → Money 변환 (Backward compatibility)
        if isinstance(pnl, (int, float)):
            if currency is None:
                currency = Currency.KRW  # Default
            pnl = Money(Decimal(str(pnl)), currency)
        
        # Daily PnL 초기화 (자정 기준)
        now = time.time()
        current_day = int(now / 86400)
        reset_day = int(self._daily_pnl_reset_time / 86400)
        
        if current_day != reset_day:
            self._daily_pnl = Money(Decimal("0"), self.base_currency)
            self._daily_pnl_reset_time = now
        
        # Base currency로 변환 후 누적
        pnl_in_base = pnl.convert_to(self.base_currency, self.fx_provider)
        self._daily_pnl += pnl_in_base
        
        # Consecutive loss 카운팅 (부호만 확인)
        if pnl.is_negative:
            if self._last_trade_pnl.is_negative:
                self._consecutive_loss_count += 1
            else:
                self._consecutive_loss_count = 1
        else:
            self._consecutive_loss_count = 0
        
        self._last_trade_pnl = pnl_in_base
        
        logger.debug(
            f"[CROSS_PNL_TRACKER] Trade added: {pnl}, "
            f"Daily PnL: {self._daily_pnl}, "
            f"Consecutive loss: {self._consecutive_loss_count}"
        )
    
    def get_daily_pnl(self) -> Money:
        """일일 PnL 조회 (Money)"""
        # Daily PnL 초기화 확인
        now = time.time()
        current_day = int(now / 86400)
        reset_day = int(self._daily_pnl_reset_time / 86400)
        
        if current_day != reset_day:
            return Money(Decimal("0"), self.base_currency)
        
        return self._daily_pnl
    
    def get_daily_pnl_amount(self) -> float:
        """일일 PnL amount 조회 (Backward compatible, float)"""
        return float(self.get_daily_pnl().amount)
    
    def get_consecutive_loss_count(self) -> int:
        """연속 손실 횟수 조회"""
        return self._consecutive_loss_count
    
    def reset_consecutive_loss(self) -> None:
        """연속 손실 카운터 리셋"""
        self._consecutive_loss_count = 0
        logger.info("[CROSS_PNL_TRACKER] Consecutive loss counter reset")
```

**CrossExchangeRiskGuardConfig 리팩토링:**

```python
@dataclass
class CrossExchangeRiskGuardConfig:
    """CrossExchangeRiskGuard 설정 (Multi-Currency)"""
    # Base currency
    base_currency: Currency = Currency.KRW
    
    # Exposure limits
    max_cross_exposure: float = 0.6
    
    # Inventory imbalance
    max_imbalance_ratio: float = 0.5
    
    # Directional bias
    max_directional_bias: float = 0.7
    min_position_count_for_bias_check: int = 3
    
    # Circuit breaker (Money 기반)
    max_daily_loss: Money = field(default_factory=lambda: Money(Decimal("5000000"), Currency.KRW))
    max_consecutive_loss: int = 5
    circuit_breaker_cooldown: float = 3600.0
    consecutive_loss_cooldown: float = 900.0
    
    # Backward compatibility: float → Money 자동 변환
    max_daily_loss_krw: Optional[float] = None
    
    def __post_init__(self):
        """max_daily_loss_krw 제공 시 Money로 변환"""
        if self.max_daily_loss_krw is not None:
            self.max_daily_loss = Money(Decimal(str(self.max_daily_loss_krw)), Currency.KRW)
            logger.warning(
                "[CONFIG] max_daily_loss_krw is deprecated. Use max_daily_loss (Money) instead."
            )
```

---

### Phase 2: Metrics 리팩토링

#### 변경 파일: `arbitrage/monitoring/cross_exchange_metrics.py`

**CrossExchangePnLSnapshot 리팩토링:**

```python
from arbitrage.common.currency import Currency, Money

@dataclass
class CrossExchangePnLSnapshot:
    """
    PnL 스냅샷 (Multi-Currency).
    
    Base Currency 기준으로 PnL 집계.
    """
    daily_pnl: Money
    unrealized_pnl: Optional[Money] = None
    consecutive_loss_count: int = 0
    win_count: int = 0
    loss_count: int = 0
    
    # Backward compatibility
    @property
    def daily_pnl_krw(self) -> float:
        """Deprecated: KRW amount (backward compatible)"""
        if self.daily_pnl.currency == Currency.KRW:
            return float(self.daily_pnl.amount)
        # 다른 통화면 경고
        logger.warning(
            f"[SNAPSHOT] daily_pnl_krw called but currency is {self.daily_pnl.currency}. "
            "Use daily_pnl (Money) instead."
        )
        return float(self.daily_pnl.amount)
    
    @property
    def unrealized_pnl_krw(self) -> float:
        """Deprecated: KRW amount (backward compatible)"""
        if self.unrealized_pnl is None:
            return 0.0
        if self.unrealized_pnl.currency == Currency.KRW:
            return float(self.unrealized_pnl.amount)
        logger.warning(
            f"[SNAPSHOT] unrealized_pnl_krw called but currency is {self.unrealized_pnl.currency}. "
            "Use unrealized_pnl (Money) instead."
        )
        return float(self.unrealized_pnl.amount)
```

**CrossExchangeMetrics.record_pnl_snapshot() 리팩토링:**

```python
def record_pnl_snapshot(self, snapshot: CrossExchangePnLSnapshot, symbol: str = "all") -> None:
    """
    PnL 스냅샷 기록 (Multi-Currency).
    
    Args:
        snapshot: CrossExchangePnLSnapshot (Money 기반)
        symbol: 심볼 이름
    """
    symbol_label = symbol if symbol else "all"
    base_currency = snapshot.daily_pnl.currency.value
    
    # Gauge: Daily PnL (새 메트릭 이름, base_currency dimension)
    self.backend.set_gauge(
        "cross_daily_pnl",
        value=float(snapshot.daily_pnl.amount),
        labels={"base_currency": base_currency, "symbol": symbol_label}
    )
    
    # Gauge: Daily PnL (구 메트릭 이름, deprecated, backward compatible)
    self.backend.set_gauge(
        "cross_daily_pnl_krw",
        value=float(snapshot.daily_pnl.amount),
        labels={"symbol": symbol_label}
    )
    
    # Gauge: Unrealized PnL
    if snapshot.unrealized_pnl is not None:
        self.backend.set_gauge(
            "cross_unrealized_pnl",
            value=float(snapshot.unrealized_pnl.amount),
            labels={"base_currency": base_currency, "symbol": symbol_label}
        )
        
        # Deprecated
        self.backend.set_gauge(
            "cross_unrealized_pnl_krw",
            value=float(snapshot.unrealized_pnl.amount),
            labels={"symbol": symbol_label}
        )
    
    # ... (나머지 메트릭은 동일)
```

---

### Phase 3: RiskGuard Exposure/Imbalance Currency-aware

**Circuit Breaker 리팩토링:**

```python
def _check_circuit_breaker(self, decision: CrossExchangeDecision) -> CrossRiskDecision:
    """
    Circuit Breaker 체크 (Multi-Currency).
    
    Daily loss / Consecutive loss 기준 BLOCK.
    """
    daily_pnl = self.pnl_tracker.get_daily_pnl()
    consecutive_loss = self.pnl_tracker.get_consecutive_loss_count()
    
    # Daily loss limit (Money 비교)
    if daily_pnl < -self.config.max_daily_loss:
        return CrossRiskDecision(
            allowed=False,
            tier="cross_exchange",
            reason_code=CrossRiskReasonCode.CROSS_DAILY_LOSS_LIMIT.value,
            details={
                "daily_pnl": str(daily_pnl),
                "max_daily_loss": str(self.config.max_daily_loss),
                "threshold": float(self.config.max_daily_loss.amount),
                "actual": float(daily_pnl.amount),
            },
        )
    
    # Consecutive loss limit
    if consecutive_loss >= self.config.max_consecutive_loss:
        return CrossRiskDecision(
            allowed=False,
            tier="cross_exchange",
            reason_code=CrossRiskReasonCode.CROSS_CONSECUTIVE_LOSS_LIMIT.value,
            details={
                "consecutive_loss_count": consecutive_loss,
                "max_consecutive_loss": self.config.max_consecutive_loss,
            },
            cooldown_until=time.time() + self.config.consecutive_loss_cooldown,
        )
    
    return CrossRiskDecision(
        allowed=True,
        tier="none",
        reason_code=CrossRiskReasonCode.OK.value,
    )
```

---

## 🧪 Testing Strategy

### 1. Backward Compatibility Tests (기존 D79 테스트 72개)
- **목표**: 100% PASS 유지
- **방법**: float → Money 자동 변환 검증

### 2. 신규 D80-1 Tests (15개)

#### A. PnLTracker Tests (5)
1. `test_pnl_tracker_money_addition`: Money 기반 PnL 누적
2. `test_pnl_tracker_multi_currency_conversion`: USD + KRW → KRW 변환 집계
3. `test_pnl_tracker_backward_compat_float`: float 자동 KRW 변환
4. `test_pnl_tracker_consecutive_loss_with_money`: Money 기반 연속 손실
5. `test_pnl_tracker_daily_reset_with_money`: 일일 리셋 Money 유지

#### B. RiskGuard Tests (5)
6. `test_risk_guard_daily_loss_limit_money`: Money 기반 Daily loss limit
7. `test_risk_guard_multi_currency_pnl_block`: USD 손실 → KRW 변환 후 BLOCK
8. `test_risk_guard_config_backward_compat`: max_daily_loss_krw → Money 자동 변환
9. `test_risk_guard_consecutive_loss_money`: Money 기반 Consecutive loss
10. `test_risk_guard_exposure_multi_currency`: KRW + USDT 잔고 Exposure (미구현, 향후)

#### C. Metrics Tests (5)
11. `test_metrics_pnl_snapshot_money`: Money 기반 PnL 스냅샷 기록
12. `test_metrics_base_currency_dimension`: base_currency label 포함 확인
13. `test_metrics_backward_compat_krw_suffix`: _krw suffix 메트릭 유지
14. `test_metrics_multi_currency_snapshot`: USD base currency 메트릭
15. `test_metrics_pnl_snapshot_property_deprecation`: daily_pnl_krw property 경고

---

## 📝 Migration Checklist

### Core Files
- [ ] `arbitrage/cross_exchange/risk_guard.py`
  - [ ] CrossExchangePnLTracker 리팩토링
  - [ ] CrossExchangeRiskGuardConfig 리팩토링
  - [ ] _check_circuit_breaker Money 비교
- [ ] `arbitrage/monitoring/cross_exchange_metrics.py`
  - [ ] CrossExchangePnLSnapshot 리팩토링
  - [ ] record_pnl_snapshot base_currency dimension

### Test Files
- [ ] `tests/test_d80_1_core_integration.py` (NEW, 15 tests)
- [ ] 기존 D79 테스트 72/72 PASS 확인

### Documentation
- [ ] `docs/D80_1_CORE_REFACTOR_DESIGN.md` (이 파일)
- [ ] `D_ROADMAP.md` 업데이트

---

## ⚠️ Risks & Mitigations

### Risk 1: 기존 테스트 FAIL
- **Mitigation**: Backward compatibility layer (float → Money 자동 변환)
- **Verification**: D79 테스트 72/72 PASS 확인

### Risk 2: FxRateProvider 의존성
- **Mitigation**: StaticFxRateProvider fallback, 환율 미제공 시 경고만
- **Verification**: 환율 없어도 동작 (KRW only 시나리오)

### Risk 3: Money 객체 생성 overhead
- **Mitigation**: Decimal 캐싱, 필요 시점에만 Money 생성
- **Verification**: 성능 벤치마크 (목표: < 10% overhead)

---

## 📦 Deliverables (D80-1)

1. ✅ `docs/D80_1_CORE_REFACTOR_DESIGN.md` (이 문서)
2. ⏳ `arbitrage/cross_exchange/risk_guard.py` (MODIFIED, PnLTracker + Config)
3. ⏳ `arbitrage/monitoring/cross_exchange_metrics.py` (MODIFIED, Snapshot + Metrics)
4. ⏳ `tests/test_d80_1_core_integration.py` (NEW, 15 tests)
5. ⏳ `D_ROADMAP.md` (MODIFIED, D80-1 완료 상태)
6. ⏳ Git commit: `[D80-1] Multi-Currency Core Integration COMPLETE`

---

## 🎓 Key Design Decisions

### 1. Backward Compatibility First
- float → Money 자동 변환으로 기존 코드 100% 동작
- 기존 메트릭 이름 유지 (deprecated, 병행 사용)

### 2. Base Currency 명시적 관리
- PnLTracker, Config, Snapshot 모두 base_currency 속성
- 기본값 Currency.KRW (하위 호환)

### 3. Money vs float 혼용 허용
- `add_trade(pnl: Union[Money, float])`로 양쪽 지원
- float 사용 시 deprecation warning

### 4. Metrics 점진적 전환
- 새 메트릭 이름 (`cross_daily_pnl`) + 구 메트릭 이름 (`cross_daily_pnl_krw`) 병행
- D80-2 이후 구 메트릭 제거 계획

---

**End of Document**
