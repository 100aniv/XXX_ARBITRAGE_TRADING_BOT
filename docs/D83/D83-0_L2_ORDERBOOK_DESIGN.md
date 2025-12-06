# D83-0: L2 Orderbook Integration – Real Fill Input Baseline

**Status:** 🚀 **IN PROGRESS**  
**Date:** 2025-12-06  
**Objective:** Fill Model 26.15% 고정 문제의 근본 원인(`available_volume` 하드코딩) 해결

---

## 📋 AS-IS Analysis

### 1. 현재 `available_volume` 경로

**문제의 핵심 (executor.py Line 353-354):**

```python
# TODO(D81-x): 실제 호가 잔량을 orderbook에서 가져오기
# 현재는 보수적 기본값 사용
buy_available_volume = trade.quantity * self.default_available_volume_factor  # 2.0 기본값
sell_available_volume = trade.quantity * self.default_available_volume_factor
```

**결과:**
- BTC 거래 시 `trade.quantity = 0.0005`, `factor = 2.0`
- `available_volume = 0.001 BTC = 약 100 USDT`
- **항상 동일한 고정값** → Fill Ratio 26.15% 고정

### 2. 기존 인프라 현황

**✅ 이미 존재하는 L2 데이터:**

```python
@dataclass
class OrderBookSnapshot:
    """호가 스냅샷"""
    symbol: str
    timestamp: float
    bids: List[tuple]  # [(price, qty), ...] ← L2 데이터 존재!
    asks: List[tuple]  # [(price, qty), ...]
```

**✅ 이미 존재하는 Provider:**

```python
class MarketDataProvider(ABC):
    def get_latest_snapshot(self, symbol: str) -> Optional[OrderBookSnapshot]:
        """최신 호가 스냅샷 반환 (L2 포함)"""
```

**❌ 연결 누락:**
- `PaperExecutor`는 `MarketDataProvider`에 접근 불가
- `OrderBookSnapshot`의 L2 데이터를 사용하지 않음

### 3. Root Cause 확인

**D84-0/D84-1에서 발견한 Root Cause 재확인:**

```
Fill Model 로직 자체는 정상 (SimpleFillModel, AdvancedFillModel, CalibratedFillModel 모두 정상)
문제는 Input 데이터: `available_volume`이 하드코딩되어 실제 시장 유동성을 반영하지 못함
→ Fill Ratio = min(order_qty / available_volume, 1.0)
→ available_volume이 고정값이면 Fill Ratio도 고정값
```

---

## 🎯 D83-0 설계: L2 → available_volume 데이터 경로

### 1. 데이터 흐름 정의

**End-to-End Flow:**

```
Upbit/Binance Public API
    ↓
MarketDataProvider.get_latest_snapshot()
    ↓
OrderBookSnapshot (bids/asks 리스트, L2 포함)
    ↓
[NEW] PaperExecutor._get_available_volume_from_orderbook()
    ↓
FillContext.available_volume (실제 L2 기반 값)
    ↓
SimpleFillModel / CalibratedFillModel
    ↓
FillResult (실제 Fill Ratio, 더 이상 26.15% 고정 아님)
```

### 2. 최소 변경 원칙

**DO-NOT-TOUCH:**
- `SimpleFillModel` / `AdvancedFillModel` / `CalibratedFillModel`: **완전히 유지**
- `FillContext` 구조: **변경 없음** (backwards compatible)
- `OrderBookSnapshot` 구조: **변경 없음**
- 기존 99+ 테스트: **모두 PASS 유지**

**변경 범위:**
- `PaperExecutor` 클래스에만 최소 변경
  - `MarketDataProvider` 참조 추가 (생성자 파라미터)
  - `_get_available_volume_from_orderbook()` 메서드 추가
  - `execute_trade_with_fill_model()` Line 353-354 수정

### 3. 컴포넌트 설계

#### 3.1 PaperExecutor 확장

**생성자 수정:**

```python
class PaperExecutor(BaseExecutor):
    def __init__(
        self,
        symbol: str,
        portfolio_state: PortfolioState,
        risk_guard: RiskGuard,
        enable_fill_model: bool = False,
        fill_model: Optional[BaseFillModel] = None,
        default_available_volume_factor: float = 2.0,
        market_data_provider: Optional[MarketDataProvider] = None,  # NEW
    ):
        # ...
        self.market_data_provider = market_data_provider  # NEW
```

**새 메서드 추가:**

```python
def _get_available_volume_from_orderbook(
    self,
    symbol: str,
    side: OrderSide,
    target_price: float,
    fallback_quantity: float,
) -> float:
    """
    L2 Orderbook에서 available_volume 계산
    
    Args:
        symbol: 거래 심볼
        side: BUY or SELL
        target_price: 목표 가격
        fallback_quantity: Orderbook 없을 시 fallback (기존 로직)
    
    Returns:
        available_volume (실제 L2 기반 값)
    """
    if self.market_data_provider is None:
        # Provider 없으면 기존 fallback 로직
        return fallback_quantity * self.default_available_volume_factor
    
    snapshot = self.market_data_provider.get_latest_snapshot(symbol)
    if snapshot is None:
        return fallback_quantity * self.default_available_volume_factor
    
    # L2 Orderbook에서 available_volume 계산
    if side == OrderSide.BUY:
        # BUY: asks 사용 (매도 호가)
        levels = snapshot.asks
    else:
        # SELL: bids 사용 (매수 호가)
        levels = snapshot.bids
    
    if not levels:
        return fallback_quantity * self.default_available_volume_factor
    
    # Best Level의 volume 반환 (1단계)
    # D83-1+에서 Multi-level aggregation 추가 가능
    best_price, best_volume = levels[0]
    
    return best_volume
```

**기존 메서드 수정:**

```python
def execute_trade_with_fill_model(self, trade) -> ExecutionResult:
    """
    D80-4: Fill Model 적용 거래 실행
    """
    # [OLD] 하드코딩
    # buy_available_volume = trade.quantity * self.default_available_volume_factor
    # sell_available_volume = trade.quantity * self.default_available_volume_factor
    
    # [NEW] L2 Orderbook 기반
    buy_available_volume = self._get_available_volume_from_orderbook(
        symbol=self.symbol,
        side=OrderSide.BUY,
        target_price=trade.buy_price,
        fallback_quantity=trade.quantity,
    )
    
    sell_available_volume = self._get_available_volume_from_orderbook(
        symbol=self.symbol,
        side=OrderSide.SELL,
        target_price=trade.sell_price,
        fallback_quantity=trade.quantity,
    )
    
    # 나머지 로직 동일...
```

### 4. L2 기반 available_volume 계산 전략

**D83-0 (Baseline):**
- Best Level (첫 번째 호가) volume만 사용
- Simple & Fast
- 이미 기존 하드코딩 대비 큰 개선

**D83-1+ (Future Enhancement):**
- Multi-level aggregation (여러 호가 레벨 합산)
- Price impact 고려 (target_price 근처 레벨만)
- Dynamic depth (order_quantity 대비 필요한 레벨 수 계산)

### 5. Backwards Compatibility

**기존 코드 호환성 보장:**

```python
# market_data_provider=None이면 기존 로직 사용 (fallback)
executor = PaperExecutor(
    symbol="BTC/USDT",
    portfolio_state=state,
    risk_guard=guard,
    enable_fill_model=True,
    market_data_provider=None,  # 기존 로직
)
# → 하드코딩 로직 유지 (기존 테스트 PASS)

# market_data_provider 제공하면 L2 로직 사용
executor = PaperExecutor(
    symbol="BTC/USDT",
    portfolio_state=state,
    risk_guard=guard,
    enable_fill_model=True,
    market_data_provider=provider,  # NEW
)
# → L2 기반 available_volume 사용
```

### 6. D84-1 Infrastructure 정합성

**FillEventCollector 연동:**

```python
# FillEventCollector가 기록하는 available_volume 필드
# 이제 L2 기반 값으로 자동 채워짐
{
    "available_volume": 0.05,  # [OLD] 고정 0.001
    "filled_quantity": 0.00013,
    "fill_ratio": 0.0026,  # [NEW] 시점별로 변함
}
```

**FillModelCalibrator 호환:**

```python
# d84_1_calibration.json 생성 파이프라인
# L2 기반 데이터와도 자연스럽게 동작
# available_volume 필드가 실제 값으로 채워지므로
# Zone별 Fill Ratio 분산이 생김
```

---

## ✅ Acceptance Criteria

D83-0은 아래를 만족해야 "완료"로 판단:

### Critical (필수):

- [ ] **C1:** 하드코딩된 `available_volume` 경로 비활성화 또는 제거
- [ ] **C2:** L2 Orderbook 기반 `available_volume` 계산 경로 구현
- [ ] **C3:** 기존 테스트 99+ 개 모두 PASS (backwards compatible)
- [ ] **C4:** 새 유닛 테스트 10+ 개 작성 및 PASS

### High Priority:

- [ ] **H1:** FillEventCollector가 기록하는 `available_volume`가 시간에 따라 변함 (더 이상 고정값 아님)
- [ ] **H2:** 짧은 PAPER 스모크 테스트 (5~10분) 실행
- [ ] **H3:** Buy Fill Ratio가 26.15% 고정에서 벗어남 (분산 발생)

### Documentation:

- [ ] **D1:** `docs/D83/D83-0_L2_ORDERBOOK_REPORT.md` 작성
- [ ] **D2:** `D_ROADMAP.md` 업데이트 (D83-0 섹션 추가)
- [ ] **D3:** Git commit 완료

---

## 🚧 Implementation Plan

### Step 1: PaperExecutor 수정
- `market_data_provider` 파라미터 추가
- `_get_available_volume_from_orderbook()` 메서드 구현
- `execute_trade_with_fill_model()` Line 353-354 수정

### Step 2: 유닛 테스트 추가
- `tests/test_d83_0_l2_available_volume.py` (10+ tests)
  - Mock OrderBookSnapshot 기반 테스트
  - Best level volume 계산 검증
  - Fallback 로직 검증 (provider=None, snapshot=None)
  - BUY/SELL 양방향 테스트

### Step 3: 짧은 PAPER 스모크 테스트
- 단일 심볼 (BTC) 기준 5~10분 실행
- `FillEventCollector` 활성화
- `available_volume` 값이 시점별로 변하는지 확인
- Buy Fill Ratio 분산 발생 확인

### Step 4: 문서화
- D83-0 Report 작성
- D_ROADMAP 업데이트
- Git commit

---

## 🔍 Expected Impact

### Before (D84-1):
```
available_volume: 0.001 (고정)
fill_ratio: 0.2615 (고정)
Zone별 차이: 없음 (모두 26.15%)
```

### After (D83-0):
```
available_volume: 0.05, 0.03, 0.08, ... (실시간 변동)
fill_ratio: 0.01, 0.016, 0.005, ... (실시간 변동)
Zone별 차이: 발생 (Z1: 1.5%, Z2: 2.3%, Z4: 0.8%)
```

---

## 📌 Next Steps (D83-1+)

**D83-0은 Baseline Implementation:**
- Best level volume만 사용
- Simple & Fast

**D83-1+ Future Enhancements:**
- Multi-level volume aggregation
- Price impact 고려
- Dynamic depth calculation
- WebSocket L2 stream 최적화

---

**D83-0 설계 완료!** 이제 구현 단계로 진행합니다. 🚀
