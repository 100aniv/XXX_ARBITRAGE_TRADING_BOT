# D85-0: L2-based available_volume Integration Design

**작성일:** 2025-12-07  
**상태:** 📋 DESIGN  
**목표:** 고정 available_volume 제거, Multi L2 기반 동적 volume 계산, Cross-exchange Slippage Skeleton

---

## 1. Executive Summary

### 1.1. 문제 정의

**D84-2+ 결과:**
- Multi L2 (Upbit + Binance) WebSocket 20분+ 안정 실행 ✅
- CalibratedFillModel 정상 동작 ✅
- **하지만 available_volume = 0.002 고정 → BUY/SELL std/mean = 0.0 ❌**

**근본 원인:**
```python
# Executor._get_available_volume_from_orderbook()
snapshot = self.market_data_provider.get_latest_snapshot(symbol)  # MultiExchangeL2Snapshot
# Expects: OrderBookSnapshot (.bids, .asks)
# Actual: MultiExchangeL2Snapshot (.per_exchange dict)
# → Type mismatch → Fallback: trade.quantity * 2.0 = 0.002 (고정)
```

### 1.2. 목표

**D85-0 Scope:**
1. ✅ **고정 available_volume 제거:** Executor가 MultiExchangeL2Snapshot 지원
2. ✅ **L2 기반 동적 volume:** 실제 L2 depth에서 best exchange 선택 + volume 계산
3. ✅ **Acceptance Criteria 복구:** BUY/SELL std/mean ≥ 0.1
4. 🏗️ **Cross-exchange Slippage Skeleton:** v0 구현 (Best exchange 선택, 후속 단계 확장 준비)

**Out of Scope (D85-1+):**
- Cross-exchange 주문 분산/최적화
- Multi-level depth aggregation
- Dynamic slippage model (full implementation)

---

## 2. 설계 원칙

### 2.1. DO-NOT-TOUCH 코어
- 엔진/전략/리스크 코어 최대한 보존
- Executor/FillModel 내부만 수정
- MarketDataProvider 인터페이스 변경 없음

### 2.2. 최소 침습 (Minimum Invasive)
- 기존 동작 유지 (fallback logic)
- Opt-in 방식 (설정으로 on/off 가능)
- 단계적 확장 가능 (D85-0 → D85-1 → D85-2)

### 2.3. Type-safe & Graceful Degradation
- OrderBookSnapshot / MultiExchangeL2Snapshot 모두 지원
- Stale source / Empty orderbook → Fallback to fixed volume
- Logging/Metrics로 실제 사용 mode 추적

---

## 3. 구체 설계

### 3.1. Executor 개선

**파일:** `arbitrage/execution/executor.py`

**변경 대상:** `_get_available_volume_from_orderbook()`

**AS-IS:**
```python
def _get_available_volume_from_orderbook(...) -> float:
    snapshot = self.market_data_provider.get_latest_snapshot(symbol)
    # OrderBookSnapshot만 처리
    if side == OrderSide.BUY:
        levels = snapshot.asks  # AttributeError if MultiExchangeL2Snapshot!
    ...
```

**TO-BE:**
```python
def _get_available_volume_from_orderbook(...) -> float:
    snapshot = self.market_data_provider.get_latest_snapshot(symbol)
    
    # Type 1: OrderBookSnapshot (Upbit/Binance single L2)
    if hasattr(snapshot, 'bids') and hasattr(snapshot, 'asks'):
        return self._extract_volume_from_single_l2(snapshot, side)
    
    # Type 2: MultiExchangeL2Snapshot (Multi L2 aggregation)
    elif hasattr(snapshot, 'per_exchange'):
        return self._extract_volume_from_multi_l2(snapshot, side)
    
    # Fallback
    else:
        return fallback_quantity * self.default_available_volume_factor
```

**새 메서드 1:** `_extract_volume_from_single_l2(snapshot, side) -> float`
- 기존 로직 분리 (Best level volume 반환)

**새 메서드 2:** `_extract_volume_from_multi_l2(snapshot, side) -> float`
- MultiExchangeL2Snapshot 처리
- v0 구현: Best exchange 1개 선택 → OrderBookSnapshot 추출 → volume 반환
- 선택 전략:
  1. `best_bid_exchange` / `best_ask_exchange` 활용 (이미 aggregator가 계산)
  2. 해당 exchange의 OrderBookSnapshot에서 best level volume 추출
  3. Stale/Empty → 다음 exchange 시도 또는 fallback

### 3.2. Cross-exchange Slippage Skeleton

**v0 제약:**
- Multi L2에서 "Best exchange 1개"만 사용
- 주문 분산 없음 (전량을 best exchange에 체결 가정)

**확장 경로 (D85-1+):**
- Multi-level depth aggregation: 여러 exchange에서 동시 체결
- Order routing: Exchange별 비용/슬리피지 최소화
- Dynamic slippage model: Depth 기반 impact 예측

### 3.3. Config & CLI

**Option 1: 자동 판단 (추천)**
- Provider 타입에 따라 자동으로 Single / Multi 모드 선택
- 사용자는 `--l2-source multi`만 지정하면 됨

**Option 2: 명시적 모드 (향후)**
- `--available-volume-mode [fixed|l2_single|l2_multi]`
- D85-0에서는 Option 1로 시작

### 3.4. Logging & Metrics

**로깅 추가:**
```python
logger.debug(
    f"[D85-0_MULTI_L2] {symbol} {side.value} using {exchange_id.value} "
    f"available_volume={volume:.6f} (best_price={price:.2f})"
)
```

**Metrics (Optional):**
- Fill events JSONL에 이미 `available_volume` 필드 존재
- 추가 필요 시: `source_exchange` 필드 (어느 exchange volume 사용했는지)

---

## 4. 구현 계획

### 4.1. Phase 1: Executor 개선 (+60 lines)
- [x] `_extract_volume_from_single_l2()` 추출
- [x] `_extract_volume_from_multi_l2()` 신규
- [x] `_get_available_volume_from_orderbook()` 타입 분기 로직

### 4.2. Phase 2: 유닛 테스트 (+200 lines)
- [x] Single L2 테스트 (기존 회귀)
- [x] Multi L2 테스트 (Mock MultiExchangeL2Snapshot)
- [x] Stale source 처리 테스트
- [x] Fallback 테스트

### 4.3. Phase 3: 5분 PAPER 스모크
- [x] Duration: 300s
- [x] L2 Source: multi
- [x] Acceptance Criteria: BUY/SELL std/mean ≥ 0.1

### 4.4. Phase 4: 문서 & 커밋
- [x] D85-0 Validation Report
- [x] D_ROADMAP 업데이트
- [x] Git commit

---

## 5. Acceptance Criteria

| Criteria | 목표 | 측정 방법 |
|----------|------|----------|
| **C1. Duration** | ≥ 300초 | KPI JSON |
| **C2. Fill Events** | ≥ 40 | Fill Events JSONL |
| **C3. BUY std/mean** | ≥ 0.1 | analyze 스크립트 |
| **C4. SELL std/mean** | ≥ 0.1 | analyze 스크립트 |
| **C5. Multi L2 사용** | per_exchange volume 추출 | 로그 확인 |
| **C6. Fatal Exception** | 0 | 실행 로그 |
| **C7. 회귀 테스트** | 100% PASS | pytest |

---

## 6. Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| MultiExchangeL2Snapshot 구조 변경 | High | Type check로 graceful degradation |
| Stale source로 volume = 0 | Medium | Fallback to fixed volume |
| Best exchange 선택 로직 복잡 | Low | v0는 best_bid/ask_exchange 그대로 사용 |
| Cross-exchange 주문 분산 미구현 | Low | D85-1로 연기, Skeleton만 구현 |

---

## 7. Next Steps (D85-1+)

### D85-1: Cross-exchange Order Routing
- Multi-level depth aggregation
- Exchange별 비용 최소화 (fee + slippage)
- Split order logic

### D85-2: Dynamic Slippage Model
- Depth-based impact prediction
- Historical slippage calibration
- Adaptive alpha tuning

---

**END OF DESIGN**

**Author:** Windsurf AI (Cascade)  
**Date:** 2025-12-07  
**Status:** 📋 DESIGN READY → Implementation Phase
