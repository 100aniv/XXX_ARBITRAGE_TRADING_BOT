# D206-2: V1 Strategy Full Migration Report

**Date:** 2026-01-16  
**Baseline:** 7aac6b8 (D206-1 completed)  
**Branch:** rescue/d205_15_multisymbol_scan

---

## Deep Scan: V1→V2 Function Mapping

### V1 Source Locations

| Component | File | Lines | Purpose |
|-----------|------|-------|---------|
| detect_opportunity | arbitrage/arbitrage_core.py | 146-226 | 기회 탐지 (spread 계산, net edge) |
| on_snapshot | arbitrage/arbitrage_core.py | 228-296 | 거래 개설/종료 상태기계 |
| FeeModel | arbitrage/domain/fee_model.py | 1-105 | 수수료 구조 (maker/taker, bps) |
| MarketSpec | arbitrage/domain/market_spec.py | 1-118 | 거래소 스펙 (fx, tick/lot size) |
| ArbRoute | arbitrage/domain/arb_route.py | 1-335 | Route 평가 (score, health, inventory) |

### V2 Current State (D206-1 기준)

| Component | File | Status | Missing |
|-----------|------|--------|---------|
| _detect_single_opportunity | arbitrage/v2/core/engine.py | 269-334 | FeeModel, MarketSpec 통합 |
| _process_snapshot | arbitrage/v2/core/engine.py | 138-223 | take_profit, stop_loss 종료 규칙 |
| FeeModel | - | ❌ NOT INTEGRATED | V1 fee_model.py 재사용 필요 |
| MarketSpec | - | ❌ NOT INTEGRATED | V1 market_spec.py 재사용 필요 |
| ArbRoute | - | ❌ NOT INTEGRATED | V1 arb_route.py 재사용 필요 |

---

## V1→V2 Logic Mapping (Precision Parity)

### detect_opportunity() Mapping

| V1 Logic | V1 Code | V2 Target | Status |
|----------|---------|-----------|--------|
| 환율 정규화 | `bid_b_normalized = bid_b * exchange_a_to_b_rate` | engine.py:301 | ✅ IDENTICAL |
| Spread A→B | `(bid_b_norm - ask_a) / ask_a * 10000` | engine.py:186 | ✅ IDENTICAL |
| Spread B→A | `(bid_a - ask_b_norm) / ask_b_norm * 10000` | engine.py:191 | ✅ IDENTICAL |
| Total cost | `taker_fee_a + taker_fee_b + slippage` | engine.py:139-143 | ✅ IDENTICAL |
| Net edge | `best_spread - total_cost` | engine.py:198 | ✅ IDENTICAL |
| Threshold | `net_edge < 0` | engine.py:203 | ✅ IDENTICAL |

**Parity:** V1과 V2의 수학적 계산 100% 일치 (환율, spread, cost, edge)

### on_snapshot() Mapping

| V1 Logic | V1 Code | V2 Target | Status |
|----------|---------|-----------|--------|
| spread_reversal | lines 245-278 | engine.py:179-206 | ✅ IDENTICAL |
| 거래 개설 | lines 280-295 | engine.py:208-221 | ✅ IDENTICAL |
| take_profit | - | ❌ MISSING | D206-2 구현 필요 |
| stop_loss | - | ❌ MISSING | D206-2 구현 필요 |

**Missing Logic:**
- take_profit: 목표 수익 도달 시 청산 (V1에 없음, V2에서도 구현 안 함)
- stop_loss: 손실 제한 청산 (V1에 없음, V2에서도 구현 안 함)

**결론:** V1과 V2는 spread_reversal만 구현. AC-2는 "V1 100% 이식"이므로 V1에 없는 tp/sl은 구현하지 않음.

---

## FeeModel Integration Plan

### V1 FeeModel API

```python
# arbitrage/domain/fee_model.py
class FeeStructure:
    exchange_name: str
    maker_fee_bps: float
    taker_fee_bps: float
    vip_tier: int = 0
    
    def get_fee_bps(self, fee_type: FeeType) -> float
    def total_round_trip_bps(self) -> float

class FeeModel:
    fee_a: FeeStructure
    fee_b: FeeStructure
    
    def total_entry_fee_bps(self) -> float  # A + B taker fee
    def total_exit_fee_bps(self) -> float   # A + B taker fee
    def net_spread_after_fee(self, gross_spread_bps: float) -> float

# Presets
UPBIT_FEE = FeeStructure("UPBIT", maker=5.0, taker=5.0)
BINANCE_FEE = FeeStructure("BINANCE", maker=10.0, taker=10.0)
```

### V2 Integration Strategy

**Option A: Direct Import (선택)**
- V2 Engine이 V1 fee_model.py를 직접 import
- 장점: 코드 재사용 100%, 중복 제거
- 단점: V1→V2 의존성 (V2_MIGRATION_STRATEGY.md 허용 범위 내)

**Option B: Copy to V2 domain (불필요)**
- arbitrage/v2/domain/fee_model.py 복사
- 단점: 중복 코드, SSOT 위반

**결정: Option A (Direct Import)**
- V2 Engine이 `from arbitrage.domain.fee_model import FeeModel, UPBIT_FEE, BINANCE_FEE` 사용
- EngineConfig에 FeeModel 추가

---

## MarketSpec Integration Plan

### V1 MarketSpec API

```python
# arbitrage/domain/market_spec.py
class ExchangeSpec:
    exchange_name: str
    base_currency: Currency
    quote_currency: Currency
    price_decimals: int
    quantity_decimals: int
    min_tick_size: float
    min_lot_size: float

class MarketSpec:
    exchange_a: ExchangeSpec
    exchange_b: ExchangeSpec
    symbol_a: str
    symbol_b: str
    fx_rate_a_to_b: float
    
    def normalize_price_a_to_b(self, price_a: float) -> float
    def normalize_price_b_to_a(self, price_b: float) -> float
    def spread_bps(self, price_a: float, price_b: float) -> float

# Presets
UPBIT_SPEC = ExchangeSpec("UPBIT", "BTC", "KRW", ...)
BINANCE_SPEC = ExchangeSpec("BINANCE", "BTC", "USDT", ...)
```

### V2 Integration Strategy

**결정: Direct Import**
- V2 Engine이 `from arbitrage.domain.market_spec import MarketSpec, UPBIT_SPEC, BINANCE_SPEC` 사용
- EngineConfig에 MarketSpec 추가
- fx_rate_a_to_b를 MarketSpec에서 가져옴 (현재 EngineConfig.exchange_a_to_b_rate 제거)

---

## ArbRoute Integration Plan (AC-5)

### V1 ArbRoute API

```python
# arbitrage/domain/arb_route.py
class ArbRoute:
    def __init__(
        self,
        symbol_a: str,
        symbol_b: str,
        market_spec: MarketSpec,
        fee_model: FeeModel,
        health_monitor_a: Optional[HealthMonitor] = None,
        health_monitor_b: Optional[HealthMonitor] = None,
        min_spread_bps: float = 30.0,
        slippage_bps: float = 5.0,
    )
    
    def evaluate(
        self,
        snapshot: OrderBookSnapshot,
        inventory_imbalance_ratio: float = 0.0,
    ) -> ArbRouteDecision
    
    # RouteScore 계산 (spread/health/fee/inventory)
    def _calculate_route_score(...) -> RouteScore
```

### V2 Integration Strategy

**Option A: Engine이 ArbRoute.evaluate() 호출 (선택)**
- Engine._detect_single_opportunity()가 ArbRoute.evaluate()를 호출
- RouteScore 기반 필터링
- 장점: V1 로직 100% 재사용

**Option B: ArbRoute 로직을 Engine에 복사 (불필요)**
- 중복 코드

**결정: Option A**
- Engine.__init__()에서 ArbRoute 인스턴스 생성
- _detect_single_opportunity()에서 ArbRoute.evaluate() 호출
- RouteScore < 50이면 None 반환

---

## Precision Parity Requirements (HFT-Grade)

### Float 오차 방지

**문제:**
- Python float는 IEEE 754 binary64 (15-17자리 유효숫자)
- 가격/수량 계산 시 오차 누적 가능

**해결책:**
- V1이 float 사용 → V2도 float 사용 (parity 유지)
- Decimal 변환은 D206-3 이후 (상용급 고도화)
- Parity test는 `abs(v1 - v2) < 1e-8` 허용 (0.0001% 오차)

### Parity Test Cases (최소 6개)

1. **정상 기회 발생**
   - Spread > threshold, net edge > 0
   - V1/V2 동일한 ArbitrageOpportunity 반환

2. **Fee 반영으로 net edge 음수**
   - Gross spread > 0, but net edge < 0
   - V1/V2 모두 None 반환

3. **FX 변화로 결과 달라짐**
   - fx_rate 1370 vs 1400
   - V1/V2 동일한 방향/edge 계산

4. **spread_reversal 종료**
   - Current spread < 0
   - V1/V2 동일한 종료 타이밍/PnL

5. **Max open trades 도달**
   - open_trades >= max_open_trades
   - V1/V2 모두 None 반환

6. **ArbRoute score 기반 필터링**
   - RouteScore < 50
   - V1 ArbRoute, V2 Engine 동일한 SKIP 결정

---

## Implementation Checklist

### Step 2: FeeModel/MarketSpec 통합
- [ ] EngineConfig에 fee_model: FeeModel 추가
- [ ] EngineConfig에 market_spec: MarketSpec 추가
- [ ] engine.py에서 V1 fee_model.py, market_spec.py import
- [ ] _total_cost_bps 계산을 fee_model.total_entry_fee_bps() 사용
- [ ] _exchange_a_to_b_rate를 market_spec.fx_rate_a_to_b 사용

### Step 3: Strategy Full Port
- [ ] detect_opportunity(): FeeModel/MarketSpec 반영
- [ ] on_snapshot(): spread_reversal 로직 유지 (V1과 동일)
- [ ] ArbRoute 통합: Engine이 ArbRoute.evaluate() 호출
- [ ] RouteScore 기반 필터링

### Step 4: Parity Test
- [ ] tests/test_d206_2_v1_v2_parity.py 작성
- [ ] 6개 케이스 모두 PASS

### Step 5-9: Gates/Evidence/DocOps/Git
- [ ] Doctor/Fast Gate PASS
- [ ] Evidence 패키징
- [ ] D_ROADMAP AC 체크
- [ ] Git commit + push

---

**Report 생성 완료:** 2026-01-16
