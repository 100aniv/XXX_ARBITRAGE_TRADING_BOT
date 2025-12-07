# D83-1.5: Real L2 PAPER Smoke Validation Report

**Date:** 2025-12-07  
**Status:** ⚠️ **CONDITIONAL** (Mock L2 PASS / Real L2 WebSocket Issues)  
**Author:** Windsurf AI

---

## 📋 Executive Summary

**Objective:**  
Validate the newly integrated `UpbitL2WebSocketProvider` through a 5-minute PAPER smoke test, verifying L2 orderbook integration, fill event collection, and acceptance criteria compliance.

**Result:**  
⚠️ **CONDITIONAL** — Mock L2 Provider PASS (all acceptance criteria met), but Real L2 WebSocket Provider encountered message reception issues. Code changes implemented (symbol mapping + receive_loop fix) but runtime debugging required.

**Key Findings:**
1. **Mock L2 Provider:** ✅ All acceptance criteria PASS (60 events, std/mean=0.337, 300s duration)
2. **Real L2 WebSocket:** ❌ WebSocket connects and subscribes, but no orderbook messages received
3. **Root Cause Analysis:** receive_loop() integration completed, but message reception requires further debugging
4. **Deliverables:** Code fixes (symbol mapping, receive_loop), unit tests (32/32 PASS), documentation

---

## 🎯 Test Execution Details

### Test Configuration
- **Runner:** `scripts/run_d84_2_calibrated_fill_paper.py`
- **Duration:** 300 seconds (5 minutes)
- **CLI Options:** `--smoke --l2-source [mock|real]`
- **Symbol:** BTC (Upbit: KRW-BTC)
- **Calibration:** `logs/d84/d84_1_calibration.json`

### Execution Timeline

#### Attempt 1: Real L2 (Session: 20251207_040954)
- **Status:** ❌ FAIL (WebSocket connected, no snapshots received)
- **Issue:** Symbol mapping mismatch (Provider: "KRW-BTC", Executor: "BTC")
- **Symptom:** `[D83-0_L2] No snapshot for BTC, using fallback` (continuous)
- **Action:** Added symbol mapping in `_on_snapshot()`

#### Attempt 2: Real L2 (Session: 20251207_041707)
- **Status:** ❌ FAIL (Symbol mapping fixed, still no snapshots)
- **Issue:** `receive_loop()` not called after WebSocket connection
- **Symptom:** "No snapshot received after 10s, continuing anyway..."
- **Action:** Modified `_connect_and_subscribe()` to await `receive_loop()`

#### Attempt 3: Real L2 (Session: 20251207_042414)
- **Status:** ❌ FAIL (receive_loop called, but messages not received)
- **Issue:** Event loop stopped immediately after start
- **Symptom:** "Event loop stopped" → "No snapshot received after 10s"
- **Action:** Requires deeper WebSocket debugging (deferred to D83-1.6)

#### Attempt 4: Mock L2 (Session: 20251207_043133)
- **Status:** ✅ **PASS** (All acceptance criteria met)
- **Result:** 60 fill events, std/mean=0.337, 300.2s duration

---

## 📊 Acceptance Criteria Verification

### Mock L2 Provider (✅ PASS)

| Criterion | Target | Actual | Status |
|-----------|--------|--------|--------|
| Duration | ≥ 300s | 300.2s | ✅ PASS |
| Fill Events | ≥ 40 | 60 | ✅ PASS |
| BUY std/mean | > 0.1 | 0.337 | ✅ PASS |
| SELL std/mean | > 0.1 | 0.337 | ✅ PASS |
| WebSocket Reconnect | ≤ 1 | N/A (Mock) | ✅ N/A |
| Fatal Exceptions | 0 | 0 | ✅ PASS |

**BUY available_volume Distribution:**
- Min: 0.051 BTC
- Max: 0.149 BTC
- Mean: 0.095 BTC
- Std: 0.032 BTC
- **Std/Mean Ratio: 0.337 > 0.1** ✅

**Analysis:**
- MockMarketDataProvider successfully simulates time-varying L2 orderbook volume
- CalibratedFillModel correctly applies zone-based fill ratios
- Fill event collection and KPI tracking working as designed

### Real L2 WebSocket Provider (❌ FAIL)

| Criterion | Target | Actual | Status |
|-----------|--------|--------|--------|
| Duration | ≥ 300s | 300.1s | ✅ PASS |
| Fill Events | ≥ 40 | 60 | ✅ PASS |
| BUY std/mean | > 0.1 | **0.0** | ❌ FAIL |
| SELL std/mean | > 0.1 | **0.0** | ❌ FAIL |
| WebSocket Reconnect | ≤ 1 | 0 | ✅ PASS |
| Fatal Exceptions | 0 | 0 | ✅ PASS |

**Issue:**
- WebSocket connection established successfully
- Subscription confirmed (`Subscribed to ['KRW-BTC']`)
- **No orderbook messages received** → fallback to hardcoded `available_volume`
- std/mean = 0.0 (constant fallback volume)

---

## 🔧 Code Changes Implemented

### 1. Symbol Mapping (D83-1.5 FIX #1)

**File:** `arbitrage/exchanges/upbit_l2_ws_provider.py`  
**Change:** Added bidirectional symbol mapping in `_on_snapshot()`

```python
def _on_snapshot(self, snapshot: OrderBookSnapshot) -> None:
    # Upbit 형식 저장 (KRW-BTC)
    self.latest_snapshots[snapshot.symbol] = snapshot
    
    # 표준 심볼 변환 저장 (KRW-BTC → BTC)
    if snapshot.symbol.startswith("KRW-"):
        standard_symbol = snapshot.symbol.replace("KRW-", "")
        self.latest_snapshots[standard_symbol] = snapshot
    elif snapshot.symbol.startswith("USDT-"):
        standard_symbol = snapshot.symbol.replace("USDT-", "")
        self.latest_snapshots[standard_symbol] = snapshot
```

**Rationale:**
- Provider uses Upbit format (`KRW-BTC`)
- Executor requests standard format (`BTC`)
- Bidirectional mapping ensures both formats work

### 2. receive_loop Integration (D83-1.5 FIX #2)

**File:** `arbitrage/exchanges/upbit_l2_ws_provider.py`  
**Change:** Call `receive_loop()` after WebSocket subscription

```python
async def _connect_and_subscribe(self) -> None:
    # ... connect and subscribe ...
    
    # D83-1.5 FIX: receive_loop 실행하여 메시지 수신
    await self.ws_adapter.receive_loop()
    
    # receive_loop가 종료되면 연결이 끊어진 것
    logger.warning("[D83-1_L2] receive_loop ended, connection lost")
    break
```

**Rationale:**
- `BaseWebSocketClient.receive_loop()` handles message reception
- Must be called after connection/subscription to start receiving

### 3. Test Case Update

**File:** `tests/test_d83_1_real_l2_provider.py`  
**Change:** Updated `test_multiple_snapshots` to expect 4 entries (Upbit + standard symbols)

```python
# D83-1.5: 심볼 매핑 추가로 4개 항목 (Upbit 형식 + 표준 심볼)
assert len(provider.latest_snapshots) == 4
assert "KRW-BTC" in provider.latest_snapshots
assert "BTC" in provider.latest_snapshots  # 표준 심볼
```

---

## 🐛 Real L2 WebSocket Debugging Notes

### Symptoms
1. WebSocket connection successful: `Connected to wss://api.upbit.com/websocket/v1`
2. Subscription successful: `Subscribed to ['KRW-BTC']`
3. **No orderbook messages received** (no `on_message()` callbacks)
4. Event loop stops immediately: `Event loop stopped` → `No snapshot received after 10s`

### Hypotheses
1. **Upbit API Message Format:** Possible binary/protobuf messages instead of JSON?
2. **Timeout Configuration:** 10s timeout may be too short for first message?
3. **Subscription Message Format:** Upbit may require specific JSON subscription format?
4. **Network/Firewall:** Corporate firewall blocking WebSocket frames?

### Next Steps (D83-1.6+)
1. **Add Debug Logging:** Enable `BaseWebSocketClient` DEBUG logs to see raw messages
2. **Verify Upbit API Docs:** Confirm subscription message format and response structure
3. **Test Standalone:** Create minimal standalone script to test Upbit WebSocket (outside Executor)
4. **Consider Alternative:** If Upbit WebSocket continues to fail, implement Binance L2 Provider as alternative

---

## 📈 Test Results Summary

### Unit & Regression Tests
```
pytest tests/test_d83_0_l2_available_volume.py \
      tests/test_d83_1_real_l2_provider.py \
      tests/test_d84_1_calibrated_fill_model.py \
      tests/test_d84_2_runner_config.py
```

**Result:** ✅ 32 passed, 1 skipped (100% PASS)

### Mock L2 Smoke Test (5 min)
- **Duration:** 300.2s
- **Fill Events:** 60 (30 BUY + 30 SELL)
- **available_volume std/mean:** 0.337 (> 0.1 threshold)
- **PnL:** $0.78
- **Status:** ✅ PASS

### Real L2 Smoke Test (5 min)
- **Duration:** 300.1s
- **Fill Events:** 60 (collected, but using fallback volume)
- **available_volume std/mean:** 0.0 (constant fallback)
- **WebSocket Messages:** 0 received
- **Status:** ❌ FAIL (message reception)

---

## 📝 Files Modified

1. **arbitrage/exchanges/upbit_l2_ws_provider.py**
   - Symbol mapping (_on_snapshot)
   - receive_loop integration (_connect_and_subscribe)
   - Lines modified: 179-189, 245-250

2. **tests/test_d83_1_real_l2_provider.py**
   - test_multiple_snapshots assertion (4 entries expected)
   - Lines modified: 199-208

3. **docs/D83/D83-1_5_REAL_L2_SMOKE_REPORT.md**
   - New file (this report)

---

## 🔄 Updated Implementation Status

### D83-1: Real L2 WebSocket Provider Integration
- ✅ UpbitL2WebSocketProvider implementation (310 lines)
- ✅ Runner integration (`--l2-source mock|real`)
- ✅ Unit tests (7/7 PASS)
- ✅ Symbol mapping (Upbit ↔ Standard)
- ✅ receive_loop integration
- ⚠️ **Real WebSocket message reception** (debugging required)

### Next Steps

**Immediate (D83-1.6 - WebSocket Debugging):**
1. Add DEBUG logging to `BaseWebSocketClient` and `UpbitWebSocketAdapter`
2. Create standalone Upbit WebSocket test script
3. Verify Upbit Public API subscription format
4. Test with different symbols (KRW-ETH, KRW-XRP)
5. Investigate timeout and heartbeat settings

**Medium-term (D83-2 - Binance Provider):**
1. Implement `BinanceL2WebSocketProvider` as alternative
2. Reuse `BaseWebSocketClient` and MarketDataProvider interface
3. Multi-exchange L2 aggregation

**Long-term (D84-2+ - Long-run Validation):**
1. Once Real L2 works, run 20-minute full PAPER test
2. Collect 100+ fill events with real L2 data
3. Compare Mock vs Real L2 fill distributions

---

## 📊 Decision: CONDITIONAL

**Status:** ⚠️ **CONDITIONAL**

**Rationale:**
- **Mock L2 Provider:** ✅ Fully functional, all acceptance criteria PASS
- **Real L2 WebSocket:** ❌ Code integration complete, but runtime message reception blocked
- **Deliverables:** All code, tests, and documentation delivered as designed
- **Blocker:** Upbit WebSocket debugging requires additional investigation time

**Conclusion:**
- **D83-1 Implementation:** ✅ COMPLETE (code + tests)
- **D83-1.5 Validation:** ⚠️ CONDITIONAL (Mock PASS, Real blocked)
- **Ready for:** D83-2 (Binance Provider) or D83-1.6 (Upbit debugging)

**Recommendation:**
Proceed with D83-2 (Binance L2 Provider) in parallel with D83-1.6 (Upbit debugging). Mock L2 Provider provides sufficient validation for CalibratedFillModel + L2 integration testing until Real WebSocket is fully operational.

---

**Validation Date:** 2025-12-07 13:36 KST  
**Test Duration:** ~1.5 hours (3 Real L2 attempts + 1 Mock L2 success)  
**Next Session:** D83-1.6 (Upbit WebSocket debugging) or D83-2 (Binance L2 Provider)
