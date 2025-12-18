# D98-2 AS-IS Scan: Live Exchange State-Changing Entry Points

**Date**: 2025-12-18  
**Objective**: Identify all state-changing methods in Live Exchange adapters requiring ReadOnlyGuard protection

---

## 1. Exchange Adapter Structure

### 1.1 BaseExchange (Abstract Interface)

**File**: `arbitrage/exchanges/base.py`

**Abstract Methods** (must be implemented by all adapters):

| Method | Lines | Type | State-Changing |
|--------|-------|------|----------------|
| `get_orderbook(symbol)` | 205-216 | Query | ❌ No |
| `get_balance()` | 218-226 | Query | ❌ No |
| `create_order(...)` | 228-252 | Trading | ✅ YES |
| `cancel_order(order_id)` | 254-265 | Trading | ✅ YES |
| `get_open_positions()` | 267-275 | Query | ❌ No |
| `get_order_status(order_id)` | 277-288 | Query | ❌ No |

**State-Changing Methods**: 2 (create_order, cancel_order)

---

### 1.2 UpbitSpotExchange

**File**: `arbitrage/exchanges/upbit_spot.py`

**Implementation Summary**:
- Inherits from BaseExchange
- Uses Upbit REST API
- Has `live_enabled` flag check (not ReadOnlyGuard)
- Methods:

| Method | Lines | Type | Current Protection | ReadOnlyGuard Needed |
|--------|-------|------|-------------------|---------------------|
| `get_orderbook(symbol)` | 101-184 | Query | None | ❌ No |
| `get_balance()` | 186-263 | Query | None | ❌ No |
| `create_order(...)` | 265-399 | **Trading** | `live_enabled` check | ✅ **YES** |
| `cancel_order(order_id)` | 401-469 | **Trading** | `live_enabled` check | ✅ **YES** |
| `get_open_positions()` | 471-478 | Query | None | ❌ No |
| `get_order_status(order_id)` | 480-505 | Query | None | ❌ No |

**Current Protection Mechanism**:
```python
# Line 293-301 (create_order)
if not self.live_enabled:
    raise RuntimeError(
        "[D48_UPBIT] Live trading is disabled. "
        "Set live_enabled=True in config to enable real trading."
    )

# Line 416-421 (cancel_order)
if not self.live_enabled:
    raise RuntimeError(
        "[D48_UPBIT] Live trading is disabled. "
        "Set live_enabled=True in config to enable real trading."
    )
```

**Gap Analysis**:
- ✅ Has `live_enabled` check
- ❌ No ReadOnlyGuard decorator
- ❌ Preflight cannot force read-only mode globally
- ⚠️ `live_enabled=False` requires config change (not enforced by environment variable)

---

### 1.3 BinanceFuturesExchange

**File**: `arbitrage/exchanges/binance_futures.py`

**Implementation Summary**:
- Inherits from BaseExchange
- Uses Binance Futures REST API
- Has `live_enabled` flag check (not ReadOnlyGuard)
- Methods:

| Method | Lines | Type | Current Protection | ReadOnlyGuard Needed |
|--------|-------|------|-------------------|---------------------|
| `get_orderbook(symbol)` | 106-180 | Query | None | ❌ No |
| `get_balance()` | 182-261 | Query | None | ❌ No |
| `create_order(...)` | 263-398 | **Trading** | `live_enabled` check | ✅ **YES** |
| `cancel_order(order_id, symbol)` | 400-478 | **Trading** | `live_enabled` check | ✅ **YES** |
| `get_open_positions()` | 480-493 | Query | None | ❌ No |
| `get_order_status(order_id)` | 495-520 | Query | None | ❌ No |

**Current Protection Mechanism**:
```python
# Line 291-299 (create_order)
if not self.live_enabled:
    raise RuntimeError(
        "[D48_BINANCE] Live trading is disabled. "
        "Set live_enabled=True in config to enable real trading."
    )

# Line 416-421 (cancel_order)
if not self.live_enabled:
    raise RuntimeError(
        "[D48_BINANCE] Live trading is disabled. "
        "Set live_enabled=True in config to enable real trading."
    )
```

**Gap Analysis**:
- ✅ Has `live_enabled` check
- ❌ No ReadOnlyGuard decorator
- ❌ Preflight cannot force read-only mode globally
- ⚠️ `live_enabled=False` requires config change (not enforced by environment variable)

---

### 1.4 PaperExchange (Reference - Already Protected)

**File**: `arbitrage/exchanges/paper_exchange.py`

**Status**: ✅ Already has ReadOnlyGuard (D98-1)

| Method | Lines | Protection |
|--------|-------|-----------|
| `create_order(...)` | 113-128 | ✅ `@enforce_readonly` |
| `cancel_order(order_id)` | 240-246 | ✅ `@enforce_readonly` |

---

## 2. State-Changing Methods Inventory

### 2.1 Complete List

| Exchange | Method | File | Lines | Current Protection | D98-2 Action |
|----------|--------|------|-------|-------------------|--------------|
| **Upbit** | `create_order` | upbit_spot.py | 265-399 | `live_enabled` | ✅ Add `@enforce_readonly` |
| **Upbit** | `cancel_order` | upbit_spot.py | 401-469 | `live_enabled` | ✅ Add `@enforce_readonly` |
| **Binance** | `create_order` | binance_futures.py | 263-398 | `live_enabled` | ✅ Add `@enforce_readonly` |
| **Binance** | `cancel_order` | binance_futures.py | 400-478 | `live_enabled` | ✅ Add `@enforce_readonly` |
| **Paper** | `create_order` | paper_exchange.py | 113-128 | `@enforce_readonly` | ✅ Already done (D98-1) |
| **Paper** | `cancel_order` | paper_exchange.py | 240-246 | `@enforce_readonly` | ✅ Already done (D98-1) |

**Total State-Changing Methods**: 6  
**Already Protected (D98-1)**: 2  
**Requires D98-2 Protection**: 4

---

## 3. Other State-Changing Methods (Future Consideration)

### 3.1 Not Currently Implemented

The following methods are **not currently implemented** in our adapters but should be considered for future ReadOnlyGuard protection:

| Method | Purpose | Found In |
|--------|---------|----------|
| `withdraw(asset, amount, address)` | Withdraw funds | Not implemented |
| `set_leverage(symbol, leverage)` | Change leverage | Not implemented |
| `set_margin_mode(symbol, mode)` | Change margin mode | Not implemented |
| `close_position(symbol)` | Close futures position | Not implemented |
| `amend_order(order_id, ...)` | Modify existing order | Not implemented |

---

## 4. Caller Analysis

### 4.1 Who Calls These Methods?

**create_order** called by:
- `BaseExecutor.execute_trades()` → `Exchange.create_order()`
- `PaperRunner` → `PaperExecutor` → `PaperExchange.create_order()`
- `LiveRunner` → `LiveExecutor` → `UpbitSpotExchange.create_order()` / `BinanceFuturesExchange.create_order()`

**cancel_order** called by:
- `BaseExecutor` (position management logic)
- Risk management modules
- Manual trading commands

### 4.2 Defense Layers

With D98-2, defense becomes:

1. **Environment Variable**: `READ_ONLY_ENFORCED=true`
2. **ReadOnlyGuard Decorator**: `@enforce_readonly` on Exchange methods
3. **Exception**: `ReadOnlyError` raised before API call
4. **Existing Protection**: `live_enabled` check (secondary)

---

## 5. Implementation Strategy

### 5.1 Minimal Changes Principle

**Approach**: Add `@enforce_readonly` decorator to existing methods

**Why this works**:
- Decorator runs **before** method body
- Checks `READ_ONLY_ENFORCED` environment variable
- Raises `ReadOnlyError` if true
- Existing `live_enabled` check remains as secondary safety

**Files to modify**:
1. `arbitrage/exchanges/upbit_spot.py` (2 methods)
2. `arbitrage/exchanges/binance_futures.py` (2 methods)

### 5.2 Decorator Application Pattern

```python
# Import at top of file
from arbitrage.config.readonly_guard import enforce_readonly

# Apply to state-changing methods
class UpbitSpotExchange(BaseExchange):
    @enforce_readonly  # ← Add this
    def create_order(...):
        # Existing code unchanged
        if not self.live_enabled:
            raise RuntimeError(...)
        ...
    
    @enforce_readonly  # ← Add this
    def cancel_order(...):
        # Existing code unchanged
        if not self.live_enabled:
            raise RuntimeError(...)
        ...
```

---

## 6. Testing Strategy

### 6.1 Unit Tests (per adapter)

For each adapter (Upbit, Binance):
- ✅ create_order blocked when READ_ONLY_ENFORCED=true
- ✅ cancel_order blocked when READ_ONLY_ENFORCED=true
- ✅ create_order allowed when READ_ONLY_ENFORCED=false
- ✅ get_balance always allowed
- ✅ get_orderbook always allowed

### 6.2 Integration Tests

- ✅ Preflight sets READ_ONLY_ENFORCED=true
- ✅ Live adapters cannot create orders during preflight
- ✅ Mock/spy verifies zero real API calls

### 6.3 Regression Tests

- ✅ Core Regression SSOT: 100% PASS
- ✅ Existing tests unaffected (conftest.py fixture)

---

## 7. Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Decorator doesn't apply to override | Low | Critical | Test each adapter separately |
| live_enabled conflicts with readonly | Low | Medium | Decorator runs first, fail-safe |
| Existing tests break | Medium | High | conftest.py fixture (D98-1) |
| Preflight bypass | Low | Critical | Force READ_ONLY=true in preflight script |

---

## 8. Acceptance Criteria Checklist

- [ ] A1: Live adapters (Upbit/Binance) have `@enforce_readonly` on state-changing methods
- [ ] A2: READ_ONLY_ENFORCED=true blocks create_order/cancel_order (unit tests)
- [ ] A3: READ_ONLY_ENFORCED=false allows orders (regression tests)
- [ ] A4: Fast Gate 100% PASS
- [ ] A4: Core Regression SSOT 100% PASS
- [ ] A5: Documentation updated (AS_IS_SCAN, REPORT, CHECKPOINT, ROADMAP)
- [ ] A6: Git commit + push with evidence links

---

**Next**: Apply `@enforce_readonly` decorator to Upbit and Binance adapters
