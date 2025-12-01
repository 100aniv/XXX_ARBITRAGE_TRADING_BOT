# D80-2: Multi-Currency Exchange & Universe Integration 설계

**Status:** 🔄 IN PROGRESS  
**Created:** 2025-12-02  
**Objective:** Universe/Exchange Adapter/Executor에 Currency 메타데이터 통합

---

## 1. AS-IS 분석

### 1.1 Universe Layer (universe_provider.py)

**현재 구조:**
```python
@dataclass
class CrossSymbol:
    mapping: any  # SymbolMapping
    upbit_volume_24h: float  # Upbit 24h 거래량 (KRW)
    binance_volume_24h: float  # Binance 24h 거래량 (USDT)
    combined_score: float  # 종합 점수
```

**문제점:**
- ✗ base_currency/quote_currency 명시 없음
- ✗ 통화 정보는 주석과 암묵적 가정에만 의존
- ✗ "KRW-BTC" vs "BTCUSDT" 심볼 파싱 로직이 분산
- ✗ Multi-Currency 확장 시 재설계 필요

### 1.2 Exchange Adapters (base.py, upbit_spot.py, binance_futures.py, paper_exchange.py)

**현재 구조:**
```python
class BaseExchange(ABC):
    def __init__(self, name: str, config: Optional[Dict[str, Any]] = None):
        self.name = name
        self.config = config or {}
    
    @abstractmethod
    def get_balance(self) -> Dict[str, Balance]:
        pass  # Return: {asset: Balance(asset, free, locked)}
    
    # Currency 관련 속성/메서드 없음
```

**문제점:**
- ✗ base_currency 속성 없음
- ✗ Money 생성 유틸 없음
- ✗ Upbit: KRW, Binance: USDT 암묵적 가정
- ✗ PaperExchange: float 잔고, Money 지원 없음

### 1.3 Executor (executor.py)

**현재 구조:**
```python
@dataclass
class CrossExecutionResult:
    decision: CrossExchangeDecision
    upbit: LegExecutionResult
    binance: LegExecutionResult
    status: Literal[...]
    pnl_krw: Optional[float] = None  # ✗ float, not Money
    # ...

class CrossExchangeExecutor:
    DEFAULT_NOTIONAL_KRW = 100_000_000  # ✗ 하드코딩
    
    def _build_order_sizes(self, decision):
        # notional 계산: float 기반
        pass
```

**문제점:**
- ✗ pnl_krw: float (Money 아님)
- ✗ notional/비용 계산 Currency-aware 아님
- ✗ D80-1 PnLTracker는 Money 지원하나, Executor는 미지원

---

## 2. TO-BE 설계

### 2.1 Universe Layer: Currency 메타데이터 추가

**목표:**
- CrossSymbol에 `base_currency`, `quote_currency` 추가
- 명시적 Currency 관리

**TO-BE 구조:**
```python
from arbitrage.common.currency import Currency

@dataclass
class CrossSymbol:
    mapping: any  # SymbolMapping
    base_currency: Currency  # NEW: KRW, USDT, etc.
    quote_currency: Currency  # NEW: BTC, ETH, etc. (optional)
    upbit_volume_24h: float
    binance_volume_24h: float
    combined_score: float
```

**Backward Compatibility:**
- `base_currency` 기본값: `Currency.KRW`
- 기존 생성자 호출 시 자동으로 KRW 할당

**변경 파일:**
- `arbitrage/cross_exchange/universe_provider.py` (~30 lines)

---

### 2.2 Exchange Adapters: Money 생성 Helper

**목표:**
- BaseExchange에 `base_currency` 속성 추가
- Money 생성 헬퍼 메서드 추가

**TO-BE 구조:**
```python
from decimal import Decimal
from arbitrage.common.currency import Money, Currency, FxRateProvider

class BaseExchange(ABC):
    def __init__(self, name: str, config: Optional[Dict[str, Any]] = None):
        self.name = name
        self.config = config or {}
        self.base_currency: Currency = self._infer_base_currency()  # NEW
    
    def _infer_base_currency(self) -> Currency:
        """거래소별 기본 통화 추론 (Upbit=KRW, Binance=USDT, etc.)"""
        pass
    
    def make_money(
        self,
        amount: Decimal | float | int,
        currency: Optional[Currency] = None
    ) -> Money:
        """Money 객체 생성 헬퍼 (NEW)"""
        if currency is None:
            currency = self.base_currency
        return Money(Decimal(str(amount)), currency)
```

**구현 세부 사항:**
- **UpbitSpotExchange:**
  - `base_currency = Currency.KRW`
  - `make_money(10000) → Money(Decimal("10000"), Currency.KRW)`
- **BinanceFuturesExchange:**
  - `base_currency = Currency.USDT`
  - `make_money(100) → Money(Decimal("100"), Currency.USDT)`
- **PaperExchange:**
  - `base_currency = Currency.KRW` (기본값)
  - Config로 변경 가능: `config={"base_currency": "USDT"}`

**변경 파일:**
- `arbitrage/exchanges/base.py` (~40 lines)
- `arbitrage/exchanges/upbit_spot.py` (~20 lines)
- `arbitrage/exchanges/binance_futures.py` (~20 lines)
- `arbitrage/exchanges/paper_exchange.py` (~30 lines)

---

### 2.3 Executor: Currency-aware 주문 금액 계산

**목표:**
- Executor에서 주문 notional/비용을 Money 기반으로 계산
- pnl_krw → pnl (Money)로 확장 준비

**TO-BE 구조:**
```python
from arbitrage.common.currency import Money, Currency, FxRateProvider

@dataclass
class CrossExecutionResult:
    decision: CrossExchangeDecision
    upbit: LegExecutionResult
    binance: LegExecutionResult
    status: Literal[...]
    pnl: Optional[Money] = None  # NEW: Money 기반 PnL
    pnl_krw: Optional[float] = None  # DEPRECATED: backward compat
    # ...
    
    @property
    def pnl_krw_amount(self) -> float:
        """DEPRECATED: backward compatible accessor"""
        return float(self.pnl.amount) if self.pnl else 0.0

class CrossExchangeExecutor:
    def __init__(self, ..., fx_provider: Optional[FxRateProvider] = None):
        # ...
        self.fx_provider = fx_provider or StaticFxRateProvider({...})
        self.base_currency = Currency.KRW  # Default
    
    def _estimate_order_cost(
        self,
        exchange: BaseExchange,
        symbol: str,
        price: float,
        qty: float
    ) -> Money:
        """주문 비용 추정 (NEW: Money 기반)"""
        notional = Decimal(str(price)) * Decimal(str(qty))
        return exchange.make_money(notional)
    
    def _build_order_sizes(self, decision):
        # Upbit notional: Money(KRW)
        upbit_cost = self._estimate_order_cost(
            self.upbit_client, decision.symbol_upbit, ...
        )
        
        # Binance notional: Money(USDT)
        binance_cost = self._estimate_order_cost(
            self.binance_client, decision.symbol_binance, ...
        )
        
        # Base currency로 통합 (D80-1 PnLTracker와 동일)
        upbit_cost_base = upbit_cost.convert_to(self.base_currency, self.fx_provider)
        binance_cost_base = binance_cost.convert_to(self.base_currency, self.fx_provider)
        
        # ...
```

**Backward Compatibility:**
- `pnl_krw` 필드 유지 (deprecated)
- 기존 코드에서 `result.pnl_krw` 호출 시 자동으로 `pnl.amount` 반환
- 신규 코드는 `result.pnl` (Money) 사용 권장

**변경 파일:**
- `arbitrage/cross_exchange/executor.py` (~80 lines)

---

## 3. 테스트 전략

### 3.1 신규 테스트 파일: `tests/test_d80_2_exchange_universe_integration.py`

**테스트 구조 (약 15~20개):**

#### A. Universe Tests (4~6 tests)
1. ✅ CrossSymbol에 base_currency 설정 (Upbit KRW)
2. ✅ CrossSymbol에 base_currency 설정 (Binance USDT)
3. ✅ base_currency 기본값 (Currency.KRW)
4. ✅ Import test: Currency + CrossSymbol 통합

#### B. Exchange Adapter Tests (6~8 tests)
5. ✅ BaseExchange.base_currency 속성 존재
6. ✅ UpbitSpotExchange.base_currency == Currency.KRW
7. ✅ BinanceFuturesExchange.base_currency == Currency.USDT
8. ✅ PaperExchange.base_currency (기본값 KRW)
9. ✅ PaperExchange.base_currency (config로 USDT 변경)
10. ✅ BaseExchange.make_money() 헬퍼 동작
11. ✅ Upbit.make_money(10000) → Money(Decimal("10000"), Currency.KRW)
12. ✅ Binance.make_money(100) → Money(Decimal("100"), Currency.USDT)

#### C. Executor Tests (4~6 tests)
13. ✅ Executor._estimate_order_cost() → Money 반환
14. ✅ Upbit notional: Money(KRW)
15. ✅ Binance notional: Money(USDT)
16. ✅ CrossExecutionResult.pnl (Money)
17. ✅ CrossExecutionResult.pnl_krw (deprecated, backward compat)
18. ✅ 기존 executor 인터페이스 유지 (import, basic flow)

### 3.2 회귀 테스트
- 전체 테스트: D79 (72) + D80-0 (41) + D80-1 (16) + D80-2 (~18) = **147+ tests**
- 목표: **ALL PASS**

---

## 4. Migration Plan

### Phase 1: Universe Layer (Step 2)
- [ ] CrossSymbol에 `base_currency`, `quote_currency` 추가
- [ ] CrossExchangeUniverseProvider에서 Currency 설정
- [ ] 테스트 4~6개 작성 및 실행

### Phase 2: Exchange Adapters (Step 3)
- [ ] BaseExchange에 `base_currency` + `make_money()` 추가
- [ ] Upbit/Binance/Paper adapters 통합
- [ ] 테스트 6~8개 작성 및 실행

### Phase 3: Executor (Step 4)
- [ ] Executor에 `_estimate_order_cost()` 추가
- [ ] `pnl` (Money) 필드 추가, `pnl_krw` deprecated
- [ ] 테스트 4~6개 작성 및 실행

### Phase 4: Full Regression (Step 5)
- [ ] D79 + D80-0 + D80-1 + D80-2 전체 테스트 실행
- [ ] 147+ tests ALL PASS

### Phase 5: Documentation & Commit (Step 6~7)
- [ ] D_ROADMAP.md 업데이트
- [ ] 본 문서 보완
- [ ] Git commit

---

## 5. Risks & Mitigations

### Risk 1: Backward Compatibility 깨짐
**Mitigation:**
- 모든 새 필드/메서드는 optional 또는 기본값 제공
- Deprecated 필드 유지 (pnl_krw 등)
- 기존 D79 테스트 72/72 유지 필수

### Risk 2: Type Mismatch (float vs Money)
**Mitigation:**
- Money ↔ float 변환 헬퍼 제공
- Property로 backward compatible accessor 제공
- 테스트에서 type 검증

### Risk 3: FxRateProvider 누락
**Mitigation:**
- StaticFxRateProvider 기본값 제공
- D80-3에서 Real FX Provider 도입

---

## 6. Next Steps (D80-3)

### D80-3: Real FX Rate Provider
- Binance FX API 연동 (USDT/USD → KRW)
- 외부 환율 API 연동 (fallback)
- FX Rate 캐싱 + Staleness 감지
- FxRateProvider 실시간 업데이트

---

## 7. 예상 변경 라인 수

| 파일 | 예상 변경 |
|------|----------|
| `arbitrage/cross_exchange/universe_provider.py` | +30 lines |
| `arbitrage/exchanges/base.py` | +40 lines |
| `arbitrage/exchanges/upbit_spot.py` | +20 lines |
| `arbitrage/exchanges/binance_futures.py` | +20 lines |
| `arbitrage/exchanges/paper_exchange.py` | +30 lines |
| `arbitrage/cross_exchange/executor.py` | +80 lines |
| `tests/test_d80_2_exchange_universe_integration.py` | +400 lines (NEW) |
| `docs/D80_2_EXCHANGE_UNIVERSE_INTEGRATION_DESIGN.md` | +300 lines (THIS) |
| `D_ROADMAP.md` | +20 lines |
| **Total** | **+940 lines** |

---

**END OF D80-2 DESIGN**
