# D79-3: Cross-Exchange Engine Integration (Paper Mode)

**Status:** ✅ **COMPLETE**  
**Date:** 2025-12-01  
**Owner:** Arbitrage Bot Team

---

## 📋 Summary

D75 Engine Loop에 CrossExchange 계층을 통합하는 얇은 Integration Layer 구현.

**구현 완료:**
1. ✅ CrossExchangeIntegration (integration layer)
2. ✅ Entry/Exit tick 메커니즘
3. ✅ D75/D78 Infrastructure 연동
4. ✅ Paper 모드 검증 (실 주문 없음)
5. ✅ Unit Tests (7/7 PASS)

**Next (D79-4):**
- Real order execution (Upbit/Binance API)
- Partial fill handling
- Rollback logic

---

## 🏗️ Architecture

### 전체 구조도

```
┌─────────────────────────────────────────────────────────┐
│               D75 Engine Loop (live_runner.py)           │
│                                                           │
│  Main Loop:                                               │
│  1. build_snapshot() → OrderBookSnapshot                │
│  2. process_snapshot() → List[ArbitrageTrade]           │
│  3. execute_trades() → Order execution                   │
└─────────────────────────────────────────────────────────┘
                          ↓ (future hook point)
┌─────────────────────────────────────────────────────────┐
│            CrossExchangeIntegration (D79-3)              │
│                                                           │
│  Responsibilities:                                        │
│  - Universe selection                                    │
│  - Spread calculation                                    │
│  - Entry/Exit signal generation                          │
│  - Position management                                   │
│  - Health/Secrets validation                             │
│                                                           │
│  Public API:                                              │
│  - tick_entry(context) → List[CrossExchangeDecision]    │
│  - tick_exit(context) → List[CrossExchangeDecision]     │
└─────────────────────────────────────────────────────────┘
        ↓                    ↓                    ↓
┌───────────────┐  ┌───────────────┐  ┌───────────────┐
│ D79-1 Modules │  │ D79-2 Modules │  │ D75/D78 Infra │
│               │  │               │  │               │
│ - Universe    │  │ - Strategy    │  │ - HealthMon   │
│ - SpreadModel │  │ - PositionMgr │  │ - RiskGuard   │
│ - FXConverter │  │               │  │ - Settings    │
└───────────────┘  └───────────────┘  └───────────────┘
```

---

## 🔄 Data Flow

### Entry Flow

```
┌─────────────────┐
│ Universe        │
│ Selection       │ → [KRW-BTC, KRW-ETH, ...]
└────────┬────────┘
         ↓
┌─────────────────┐
│ For each symbol │
│                 │
│ 1. Spread calc  │ → CrossSpread
│ 2. Health check │ → health_ok
│ 3. FX check     │ → fx_confidence
│ 4. Secrets val  │ → secrets_available
│ 5. Liquidity    │ → liquidity_ok
└────────┬────────┘
         ↓
┌─────────────────┐
│ Strategy        │
│ evaluate_entry()│ → CrossExchangeSignal
└────────┬────────┘
         ↓
    ENTRY signal?
         ↓ (YES)
┌─────────────────┐
│ Position        │
│ Manager         │
│ open_position() │ → CrossExchangePosition (Redis SSOT)
└────────┬────────┘
         ↓
┌─────────────────┐
│ Decision        │
│ (Paper mode)    │ → CrossExchangeDecision
└─────────────────┘
```

### Exit Flow

```
┌─────────────────┐
│ Position        │
│ Manager         │
│ list_open()     │ → [Position1, Position2, ...]
└────────┬────────┘
         ↓
┌─────────────────┐
│ For each        │
│ position        │
│                 │
│ 1. Calc spread  │ → CrossSpread (current)
│ 2. Health check │ → health_ok
└────────┬────────┘
         ↓
┌─────────────────┐
│ Strategy        │
│ evaluate_exit() │ → CrossExchangeSignal
└────────┬────────┘
         ↓
    EXIT signal?
         ↓ (YES)
┌─────────────────┐
│ Position        │
│ Manager         │
│ close_position()│ → CrossExchangePosition (closed)
└────────┬────────┘
         ↓
┌─────────────────┐
│ Decision        │
│ (Paper mode)    │ → CrossExchangeDecision
└─────────────────┘
```

---

## 📦 Components

### 1. CrossExchangeIntegration

**파일:** `arbitrage/cross_exchange/integration.py` (~480 lines)

**주요 메서드:**

```python
class CrossExchangeIntegration:
    def __init__(
        self,
        universe_provider: CrossExchangeUniverseProvider,
        spread_model: SpreadModel,
        fx_converter: FXConverter,
        strategy: CrossExchangeStrategy,
        position_manager: CrossExchangePositionManager,
        health_monitor: HealthMonitor,
        settings: Settings,
    ):
        ...
    
    def tick_entry(self, context: Optional[Dict] = None) -> List[CrossExchangeDecision]:
        """Entry tick: 새로운 포지션 진입 기회 평가"""
        ...
    
    def tick_exit(self, context: Optional[Dict] = None) -> List[CrossExchangeDecision]:
        """Exit tick: 기존 포지션 청산 기회 평가"""
        ...
```

**Features:**
- Universe selection (UniverseProvider)
- Spread calculation (SpreadModel + FXConverter)
- Entry/Exit signal generation (Strategy)
- Position management (PositionManager)
- Health/Secrets validation (D75/D78)
- Metrics tracking

### 2. CrossExchangeDecision

**파일:** `arbitrage/cross_exchange/integration.py`

**정의:**

```python
@dataclass
class CrossExchangeDecision:
    """Paper 모드 의사결정 (실 주문 없음)"""
    action: CrossExchangeAction
    symbol_upbit: str
    symbol_binance: str
    notional_krw: float
    spread_percent: float
    reason: str
    timestamp: float
    
    # Entry-specific
    entry_side: Optional[str] = None  # "positive" or "negative"
    
    # Exit-specific
    exit_pnl_krw: Optional[float] = None
    position_holding_time: Optional[float] = None
```

**용도:**
- Paper 모드에서 Entry/Exit 의사결정 표현
- 테스트 검증용
- 로그 기록용
- D79-4에서 실제 주문으로 변환 예정

---

## 🔗 Integration Points

### D75 Infrastructure

**1. HealthMonitor**
```python
health_ok = self._check_health()
# → health_monitor.get_status("upbit")
# → health_monitor.get_status("binance")
# → HEALTHY or DEGRADED 허용
```

**2. RiskGuard** (future)
```python
# D79-4에서 추가 예정
risk_guard.check_cross_exchange_trade(decision)
```

### D78 Secrets Layer

**Settings validation:**
```python
secrets_available = self._check_secrets()
# → settings.upbit_access_key
# → settings.binance_api_key
# → API keys 존재 여부 확인
```

### D79-1 Modules

**1. UniverseProvider:**
```python
symbol_mappings = universe_provider.select_universe(
    upbit_client=upbit_client,
    binance_client=binance_client,
)
```

**2. SpreadModel:**
```python
spread = spread_model.calculate_spread(
    upbit_price_krw=upbit_ticker.price,
    binance_price_usdt=binance_ticker.price,
    ...
)
```

**3. FXConverter:**
```python
fx_rate = fx_converter.get_fx_rate()
fx_confidence = fx_rate.confidence
```

### D79-2 Modules

**1. Strategy:**
```python
# Entry
signal = strategy.evaluate_entry(
    symbol_mapping=mapping,
    cross_spread=spread,
    fx_confidence=fx_confidence,
    health_ok=health_ok,
    secrets_available=secrets_available,
)

# Exit
signal = strategy.evaluate_exit(
    position=position,
    current_spread=spread,
    health_ok=health_ok,
)
```

**2. PositionManager:**
```python
# Open
position = position_manager.open_position(
    symbol_mapping=mapping,
    entry_side="positive",
    entry_spread=spread,
)

# Close
closed_position = position_manager.close_position(
    upbit_symbol="KRW-BTC",
    exit_spread_percent=0.2,
    exit_reason="TP",
)
```

---

## 📊 Scenarios (Paper Mode)

### Scenario 1: POSITIVE Entry → TP Exit

**Step 1: Entry Tick**
```
Universe: [KRW-BTC]
Spread: +0.8% (Upbit > Binance)
Health: OK
FX confidence: 1.0
Secrets: Available
Liquidity: OK

→ Strategy.evaluate_entry() → ENTRY_POSITIVE
→ PositionManager.open_position()
→ Decision: ENTRY_POSITIVE
```

**Step 2: Exit Tick (after 200s)**
```
Position: entry_spread=+0.8%
Current spread: +0.3% (decreased by 0.5%)
Health: OK

→ Strategy.evaluate_exit() → EXIT_TP
→ PositionManager.close_position()
→ Decision: EXIT_TP, pnl=+500K KRW
```

### Scenario 2: NEGATIVE Entry → Reversal Exit

**Step 1: Entry Tick**
```
Spread: -0.6% (Upbit < Binance)
All validations: OK

→ Strategy.evaluate_entry() → ENTRY_NEGATIVE
→ PositionManager.open_position()
→ Decision: ENTRY_NEGATIVE
```

**Step 2: Exit Tick (after 150s)**
```
Position: entry_spread=-0.6%
Current spread: +0.2% (reversed to positive)
Health: OK

→ Strategy.evaluate_exit() → EXIT_REVERSAL
→ PositionManager.close_position()
→ Decision: EXIT_REVERSAL, pnl=+800K KRW
```

### Scenario 3: Health Degraded → NO_ACTION

**Entry Tick**
```
Spread: +0.9%
Health: DEGRADED (Upbit latency > 500ms)
FX confidence: 1.0
Secrets: Available

→ Strategy.evaluate_entry() → NO_ACTION (health degraded)
→ No position opened
→ Decision: []
```

### Scenario 4: Secrets Unavailable → NO_ACTION

**Entry Tick**
```
Spread: +0.7%
Health: OK
FX confidence: 1.0
Secrets: UNAVAILABLE (API keys not set)

→ Strategy.evaluate_entry() → NO_ACTION (secrets unavailable)
→ No position opened
→ Decision: []
```

---

## 🧪 Testing

### 테스트 커버리지

**파일:** `tests/test_d79_3_engine_integration.py` (~270 lines)

**테스트 수:** 7/7 PASS (0.18s)

**테스트 항목:**

**1. Integration Basic (2 tests)**
- ✅ Integration initialization
- ✅ Integration metrics

**2. Entry Tick (2 tests)**
- ✅ Entry tick - Universe 없음
- ✅ Entry tick - Health degraded → NO_ACTION

**3. Exit Tick (1 test)**
- ✅ Exit tick - Position 없음

**4. Real Components (1 test)**
- ✅ Integration with real components (Redis)

**5. Import (1 test)**
- ✅ Integration module import

---

## 🎯 Done Criteria

- [x] ✅ CrossExchangeIntegration 구현
- [x] ✅ Entry/Exit tick 메커니즘
- [x] ✅ D79-1/2 모듈 통합
- [x] ✅ D75/D78 Infrastructure 연동
- [x] ✅ Paper 모드 검증 (실 주문 없음)
- [x] ✅ Tests 7/7 PASS
- [x] ✅ Documentation

---

## 🚀 Next Steps (D79-4)

### D79-4: Real Order Execution

**목표:**
- Upbit/Binance API 실제 주문
- Order coordination (simultaneous execution)
- Partial fill handling
- Rollback logic

**구현 사항:**
```python
class CrossExchangeExecutor:
    def execute_decision(self, decision: CrossExchangeDecision):
        # 1. Upbit order
        upbit_order = upbit_client.place_order(...)
        
        # 2. Binance order
        binance_order = binance_client.place_order(...)
        
        # 3. Partial fill check
        if upbit_order.filled < 100% or binance_order.filled < 100%:
            # Rollback logic
            ...
```

### D79-5: Advanced Risk Management

**목표:**
- Cross-exchange exposure limits
- Inventory imbalance detection
- Circuit breaker
- Dynamic thresholds

---

## 📚 Related Documents

- [D75: Core Infrastructure](./D75_ARBITRAGE_CORE_OVERVIEW.md)
- [D75-4: ArbRoute / ArbUniverse](./D75_4_ROUTE_UNIVERSE_DESIGN.md)
- [D75-5: 4-Tier RiskGuard](./D75_5_4TIER_RISKGUARD_DESIGN.md)
- [D78: Secrets Management](./D78_VAULT_KMS_DESIGN.md)
- [D79-1: Symbol Mapping & Spread Model](./D79_CROSS_EXCHANGE_DESIGN.md)
- [D79-2: Entry/Exit Strategy](./D79_CROSS_EXCHANGE_STRATEGY_DESIGN.md)

---

**Status:** ✅ **COMPLETE** (Phase 3: Engine Integration - Paper Mode)  
**Version:** 1.0.0  
**Last Updated:** 2025-12-01
