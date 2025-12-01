# D79-2: Cross-Exchange Entry/Exit Strategy Design

**Status:** ✅ **COMPLETE**  
**Date:** 2025-12-01  
**Owner:** Arbitrage Bot Team

---

## 📋 Summary

Upbit ↔ Binance 교차 거래소 아비트라지 Entry/Exit 전략 및 Position 관리 구현.

**구현 완료:**
1. ✅ CrossExchangeStrategy (Entry/Exit logic)
2. ✅ CrossExchangePositionManager (Position SSOT)
3. ✅ Unit Tests (24/24 PASS)

**Next (Phase 3):**
- D75 Engine 통합 Hooks
- Real order execution
- D79-3: Risk Management

---

## 🏗️ Architecture

### 전체 구조도

```
┌─────────────────────────────────────────────────────────┐
│              Cross-Exchange Arbitrage Engine             │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│                   CrossExchangeStrategy                  │
│                                                           │
│  Entry Logic:                                            │
│  - Spread-based (POSITIVE / NEGATIVE)                   │
│  - Multi-validation (Secrets, Health, FX, Liquidity)    │
│                                                           │
│  Exit Logic:                                             │
│  - Spread reversal (highest priority)                   │
│  - Take Profit (TP)                                      │
│  - Stop Loss (SL)                                        │
│  - Time-based timeout                                    │
│  - Health degradation (emergency)                       │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│            CrossExchangePositionManager                  │
│                                                           │
│  SSOT: Redis `cross_position:{symbol}`                  │
│                                                           │
│  State Machine:                                          │
│  OPEN → CLOSING → CLOSED                                │
│                                                           │
│  Features:                                               │
│  - Multi-symbol support                                 │
│  - Inventory tracking                                    │
│  - PnL calculation                                       │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│                  Integration Points                      │
│                                                           │
│  - D75 RiskGuard (health check)                         │
│  - D78 Secrets Layer (API key validation)              │
│  - D79-1 SpreadModel (spread calculation)              │
│  - Redis (position SSOT)                                │
└─────────────────────────────────────────────────────────┘
```

---

## 🎯 Entry/Exit Scenarios

### Scenario 1: POSITIVE Spread Entry
```
Initial State:
- Upbit BTC: 52M KRW
- Binance BTC: 40K USDT (= 52M KRW @ 1300 rate)
- Spread: +0.5% (Upbit > Binance)

Entry Conditions:
✅ abs(spread) >= 0.5%
✅ FX confidence >= 0.8
✅ Liquidity >= 100M KRW
✅ D75 Health OK
✅ D78 Secrets available

Action:
→ ENTRY_POSITIVE
→ Upbit SELL / Binance BUY

Position Opened:
- entry_side: "positive"
- entry_spread: +0.5%
- state: OPEN
```

### Scenario 2: NEGATIVE Spread Entry
```
Initial State:
- Upbit BTC: 51M KRW
- Binance BTC: 40K USDT (= 52M KRW @ 1300 rate)
- Spread: -0.8% (Upbit < Binance)

Entry Conditions:
✅ abs(spread) >= 0.5%
✅ All validations pass

Action:
→ ENTRY_NEGATIVE
→ Upbit BUY / Binance SELL

Position Opened:
- entry_side: "negative"
- entry_spread: -0.8%
- state: OPEN
```

### Scenario 3: Exit - Spread Reversal
```
Position:
- entry_side: "positive"
- entry_spread: +1.0%

Current State:
- Spread: -0.2% (reversed to negative)

Exit Logic:
1. Check reversal first (priority)
   → current_spread < 0 (positive entry)
   → REVERSAL detected!

Action:
→ EXIT_REVERSAL
→ Position CLOSED
→ PnL: Profitable (spread reversed)
```

### Scenario 4: Exit - Take Profit
```
Position:
- entry_side: "positive"
- entry_spread: +1.0%

Current State:
- Spread: +0.3% (decreased by 0.7%)

Exit Logic:
1. Reversal check: +0.3% > 0 (no reversal)
2. TP check: spread_change = -0.7% <= -0.2% (TP threshold)
   → TP triggered!

Action:
→ EXIT_TP
→ Position CLOSED
→ PnL: +700K KRW (based on 1M base)
```

### Scenario 5: Exit - Stop Loss
```
Position:
- entry_side: "positive"
- entry_spread: +0.5%

Current State:
- Spread: +1.2% (increased by 0.7%)

Exit Logic:
1. Reversal check: no
2. TP check: spread increased (no TP)
3. SL check: spread_change = +0.7% >= +0.3% (SL threshold)
   → SL triggered!

Action:
→ EXIT_SL
→ Position CLOSED
→ PnL: -700K KRW (loss)
```

### Scenario 6: Exit - Timeout
```
Position:
- entry_side: "positive"
- entry_timestamp: 1 hour ago

Current State:
- Holding time: 3700s > 3600s (max)

Exit Logic:
1. Health check: OK
2. Timeout check: 3700s > 3600s
   → Timeout!

Action:
→ EXIT_TIMEOUT
→ Position CLOSED
→ PnL: Based on current spread
```

---

## 📊 Position State Machine

```
┌─────────┐
│  OPEN   │ ← Entry signal (ENTRY_POSITIVE / ENTRY_NEGATIVE)
└────┬────┘
     │
     ├─→ (Exit signal)
     │
┌────▼────┐
│ CLOSING │ ← Order execution in progress (optional state)
└────┬────┘
     │
     ├─→ (Order completed)
     │
┌────▼────┐
│ CLOSED  │ ← Exit completed (TP/SL/Reversal/Timeout/Health)
└─────────┘

States:
- OPEN: Position active, monitoring exit conditions
- CLOSING: (Optional) Exit order submitted, waiting for fill
- CLOSED: Position closed, PnL recorded

Transitions:
1. OPEN → CLOSED (현재 구현, 단순화)
2. OPEN → CLOSING → CLOSED (Phase 3, real order execution)
```

---

## 🚨 Risk Scenarios

### Risk 1: High Latency
```
Problem:
- Upbit latency: 50ms → 500ms
- Binance latency: 20ms → 200ms

Detection:
- D75 HealthMonitor detects degradation

Strategy Response:
- evaluate_entry(): health_ok=False → NO_ACTION
- evaluate_exit(): health_ok=False → EXIT_HEALTH (emergency)

Result:
→ No new positions
→ Existing positions emergency exit
```

### Risk 2: FX Confidence Low
```
Problem:
- Upbit USDT ticker unavailable
- BTC ratio unreliable
- FX confidence: 0.5 (< 0.8 threshold)

Strategy Response:
- evaluate_entry(): fx_confidence=0.5 → NO_ACTION

Result:
→ No entry until FX confidence recovers
```

### Risk 3: Inventory Imbalance
```
Problem:
- 10 POSITIVE positions open
- 0 NEGATIVE positions
- Heavy inventory on Binance (BUY side)

PositionManager Response:
- get_inventory(): {"positive": 10, "negative": 0}

Strategy Response (future):
- Bias towards NEGATIVE entry
- Or block POSITIVE entry temporarily

Result:
→ Balanced inventory
```

### Risk 4: Secrets Unavailable
```
Problem:
- D78 Secrets Layer: API keys not loaded

Strategy Response:
- evaluate_entry(): secrets_available=False → NO_ACTION

Result:
→ No trading until secrets available
→ Fail-safe mechanism
```

---

## 🔗 Integration Flow (D75 Engine)

### Current State (D79-2)
```python
# Standalone usage (testing)
from arbitrage.cross_exchange import (
    CrossExchangeStrategy,
    CrossExchangePositionManager,
)

strategy = CrossExchangeStrategy(
    min_spread_percent=0.5,
    tp_spread_percent=0.2,
    sl_spread_percent=-0.3,
)

pm = CrossExchangePositionManager(redis_client=redis_client)

# Entry evaluation
signal = strategy.evaluate_entry(
    symbol_mapping=mapping,
    cross_spread=spread,
    fx_confidence=1.0,
    health_ok=True,
    secrets_available=True,
)

if signal.action == CrossExchangeAction.ENTRY_POSITIVE:
    position = pm.open_position(
        symbol_mapping=mapping,
        entry_side="positive",
        entry_spread=spread,
    )
```

### Future Integration (D79-3)
```python
# D75 Engine hook (planned)
from arbitrage.engine import ArbitrageEngine

engine = ArbitrageEngine(...)

# Register cross-exchange components
engine.register_cross_exchange_strategy(strategy)
engine.register_cross_exchange_position_manager(pm)

# Engine main loop
while True:
    # 1. Spread calculation (D79-1)
    spread = spread_model.calculate_spread(...)
    
    # 2. Entry signal (D79-2)
    signal = strategy.evaluate_entry(...)
    
    # 3. Position management (D79-2)
    if signal.action in [ENTRY_POSITIVE, ENTRY_NEGATIVE]:
        pm.open_position(...)
    
    # 4. Exit monitoring
    for position in pm.list_open_positions():
        exit_signal = strategy.evaluate_exit(position, current_spread)
        if exit_signal.action != NO_ACTION:
            pm.close_position(...)
```

---

## 📝 Example Logs (Paper Mode)

### Entry Log
```
[CROSS_STRATEGY] Entry signal: KRW-BTC
  - Action: ENTRY_POSITIVE
  - Spread: +0.68%
  - FX confidence: 1.0
  - Health: OK
  - Liquidity: 500M KRW

[CROSS_POSITION_MGR] Opened position: KRW-BTC
  - Side: positive
  - Entry spread: +0.68%
  - Entry FX: 1350.0
  - Upbit price: 52,340,000 KRW
  - Binance price: 38,740 USDT
```

### Exit Log (TP)
```
[CROSS_STRATEGY] Exit signal: KRW-BTC
  - Action: EXIT_TP
  - Current spread: +0.42%
  - Spread change: -0.26% (TP threshold: -0.20%)
  - Holding time: 245s

[CROSS_POSITION_MGR] Closed position: KRW-BTC
  - Reason: TP
  - PnL: +260,000 KRW
  - Holding time: 245s
  - Final spread: +0.42%
```

### Exit Log (Reversal)
```
[CROSS_STRATEGY] Exit signal: KRW-BTC
  - Action: EXIT_REVERSAL
  - Current spread: -0.15% (reversed from +0.55%)
  - Spread change: -0.70%

[CROSS_POSITION_MGR] Closed position: KRW-BTC
  - Reason: Spread reversal
  - PnL: +700,000 KRW (profitable reversal)
  - Holding time: 180s
```

---

## 🧪 Testing

### 테스트 커버리지

**파일:** `tests/test_d79_strategy.py`

**테스트 수:** 24/24 PASS (0.14s)

**테스트 항목:**

**1. CrossExchangeStrategy (14 tests)**
- ✅ Strategy initialization
- ✅ Entry signal - Positive spread
- ✅ Entry signal - Negative spread
- ✅ Entry blocked - Secrets unavailable (D78)
- ✅ Entry blocked - Health degraded (D75)
- ✅ Entry blocked - FX confidence low
- ✅ Entry blocked - Low liquidity
- ✅ Entry blocked - Spread too low
- ✅ Exit - TP (positive entry)
- ✅ Exit - SL (positive entry)
- ✅ Exit - Timeout
- ✅ Exit - Health degraded (emergency)
- ✅ Exit - Spread reversal
- ✅ Exit - No action

**2. CrossExchangePositionManager (10 tests)**
- ✅ PositionManager initialization
- ✅ Open position
- ✅ Close position
- ✅ Get position
- ✅ Get position (not found)
- ✅ List open positions
- ✅ Get inventory
- ✅ Position holding time
- ✅ Position serialization (to_dict/from_dict)
- ✅ Integration test

---

## 🎯 Done Criteria

- [x] ✅ CrossExchangeStrategy 구현
- [x] ✅ Entry logic (POSITIVE/NEGATIVE)
- [x] ✅ Exit logic (Reversal/TP/SL/Timeout/Health)
- [x] ✅ CrossExchangePositionManager 구현
- [x] ✅ Position SSOT (Redis)
- [x] ✅ Position state machine
- [x] ✅ Inventory tracking
- [x] ✅ Tests 24/24 PASS
- [x] ✅ D75 RiskGuard integration (health check)
- [x] ✅ D78 Secrets Layer integration
- [x] ✅ Documentation

---

## 🔄 Next Steps (Phase 3)

### D79-3: D75 Engine Integration
**목표:**
- Engine hooks implementation
- Main loop integration
- Real-time monitoring

**구현 사항:**
- `ArbitrageEngine.register_cross_exchange_strategy()`
- `ArbitrageEngine.register_cross_exchange_position_manager()`
- Main loop modifications

### D79-4: Real Order Execution
**목표:**
- Upbit/Binance order placement
- Order coordination
- Partial fill handling

**구현 사항:**
- `CrossExchangeExecutor`
- `OrderCoordinator`
- Rollback logic

### D79-5: Advanced Risk Management
**목표:**
- Cross-exchange exposure limits
- Inventory imbalance detection
- Circuit breaker

**구현 사항:**
- `CrossExchangeRiskGuard`
- `InventoryTracker`
- Dynamic thresholds

---

## 📚 Related Documents

- [D75: Core Infrastructure](./D75_CORE_INFRASTRUCTURE.md)
- [D76: Alert System](./D76_ALERT_RULE_ENGINE_DESIGN.md)
- [D77: TopN Arbitrage](./D77_0_TOPN_ARBITRAGE_PAPER_DESIGN.md)
- [D78: Secrets Management](./D78_VAULT_KMS_DESIGN.md)
- [D79-1: Symbol Mapping & Spread Model](./D79_CROSS_EXCHANGE_DESIGN.md)

---

**Status:** ✅ **COMPLETE** (Phase 2: Entry/Exit Strategy)  
**Version:** 1.0.0  
**Last Updated:** 2025-12-01
