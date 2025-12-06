# D84-0: Fill Model AS-IS Analysis

**Date:** 2025-12-06  
**Status:** 📋 ANALYSIS COMPLETE

---

## 📋 Executive Summary

D82-12까지의 검증 결과, **Threshold 튜닝만으로는 D77-4 성능 재현이 불가능**하다는 것이 확정되었습니다. 근본 원인은 **Fill Model의 과도한 비관적 가정 (Buy Fill 26%)**에 있습니다. D84-0은 현재 Fill Model 인프라를 분석하고, 실제 PAPER 데이터를 기반으로 Fill Model v1을 보정하는 첫 단계입니다.

**핵심 발견:**
- 현재 Fill Model은 D80-4, D81-1에서 이미 구축됨
- 고정값 Buy Fill 26.15% 사용 중 → 74% 거래 기회 차단
- D82-9~D82-12 모든 실행에서 동일한 Fill Ratio 관측
- 실제 시장 데이터 기반 보정 필요

---

## 🏗️ 현재 Fill Model 인프라 (D80-4, D81-1)

### 코드 위치

| 모듈 | 파일 | 역할 |
|------|------|------|
| **Fill Model Core** | `arbitrage/execution/fill_model.py` | Fill Model 추상 클래스 및 구현체 |
| **Executor** | `arbitrage/execution/executor.py` | Fill Model 사용 (PaperExecutor) |
| **Trade Logger** | `arbitrage/logging/trade_logger.py` | Fill 정보 로깅 (TradeLogEntry) |
| **Settings** | `arbitrage/config/settings.py` | Fill Model 설정 |
| **Factory** | `arbitrage/execution/executor_factory.py` | Fill Model 인스턴스 생성 |

### Fill Model 클래스 구조

```python
# arbitrage/execution/fill_model.py

@dataclass
class FillContext:
    """Fill Model 입력"""
    symbol: str
    side: OrderSide  # BUY or SELL
    order_quantity: float
    target_price: float
    available_volume: float  # 호가 잔량
    slippage_alpha: float = None

@dataclass
class FillResult:
    """Fill Model 출력"""
    filled_quantity: float
    unfilled_quantity: float
    effective_price: float  # 슬리피지 반영 가격
    slippage_bps: float
    fill_ratio: float  # 0.0 ~ 1.0
    status: str  # "filled", "partially_filled", "unfilled"
```

### 구현체 2종류

#### 1️⃣ SimpleFillModel (D80-4)
- **메커니즘:** Partial Fill + Linear Slippage
- **파라미터:**
  - `enable_partial_fill`: 부분 체결 활성화 (기본: True)
  - `enable_slippage`: 슬리피지 활성화 (기본: True)
  - `default_slippage_alpha`: 슬리피지 계수 (기본: 0.0001)
- **로직:**
  ```python
  # Partial Fill
  if order_quantity <= available_volume:
      filled_qty = order_quantity  # 전량 체결
  else:
      filled_qty = available_volume  # 부분 체결
  
  # Linear Slippage
  impact_factor = filled_qty / available_volume
  slippage_ratio = alpha * impact_factor
  effective_price = target_price * (1 + slippage_ratio)  # BUY
  ```

#### 2️⃣ AdvancedFillModel (D81-1)
- **메커니즘:** Multi-level L2 Simulation + Non-linear Market Impact
- **파라미터:**
  - `num_levels`: 가상 L2 레벨 수 (기본: 5)
  - `level_spacing_bps`: 레벨 간 가격 간격 (기본: 1.0 bps)
  - `decay_rate`: 레벨별 유동성 감소 속도 (기본: 0.3)
  - `slippage_exponent`: 비선형 지수 (기본: 1.2)
- **로직:** 가상 L2 생성 → 레벨별 주문 분할 → 비선형 Slippage 적용

### Executor 통합 (PaperExecutor)

```python
# arbitrage/execution/executor.py

class PaperExecutor(BaseExecutor):
    def __init__(self, fill_model: BaseFillModel = None):
        self.fill_model = fill_model or create_default_fill_model()
    
    def _execute_single_trade(self, trade):
        # 1. 매수 Fill Model 실행
        buy_context = FillContext(
            symbol=self.symbol,
            side=OrderSide.BUY,
            order_quantity=trade.quantity,
            target_price=trade.buy_price,
            available_volume=buy_available_volume,
        )
        buy_fill_result = self.fill_model.execute(buy_context)
        
        # 2. 매도 Fill Model 실행
        sell_context = FillContext(
            symbol=self.symbol,
            side=OrderSide.SELL,
            order_quantity=buy_fill_result.filled_quantity,
            target_price=trade.sell_price,
            available_volume=sell_available_volume,
        )
        sell_fill_result = self.fill_model.execute(sell_context)
        
        # 3. PnL 계산 (Fill Model 기준)
        pnl = (sell_fill_result.effective_price - buy_fill_result.effective_price) * final_filled_qty
        
        return ExecutionResult(
            buy_fill_ratio=buy_fill_result.fill_ratio,
            sell_fill_ratio=sell_fill_result.fill_ratio,
            buy_slippage_bps=buy_fill_result.slippage_bps,
            sell_slippage_bps=sell_fill_result.slippage_bps,
            ...
        )
```

### 로깅 인프라 (TradeLogEntry)

```python
# arbitrage/logging/trade_logger.py

@dataclass
class TradeLogEntry:
    """Trade-level 로그"""
    # ... 기존 필드들 ...
    
    # D81-0: Fill Model 정보
    buy_slippage_bps: float
    sell_slippage_bps: float
    buy_fill_ratio: float  # 0.0 ~ 1.0
    sell_fill_ratio: float  # 0.0 ~ 1.0
```

---

## 🔍 D82-9~D82-12 실측 데이터

### D82-9 Cost Profile (logs/d82-10/d82_9_cost_profile.json)

| 항목 | 값 | 출처 |
|------|-----|------|
| **Buy Fill Ratio (평균)** | **26.15%** | D82-9 5 candidates, 10min each |
| **Buy Fill Ratio (중간값)** | 26.15% | 동일 |
| **Buy Fill Ratio (p25)** | 26.15% | 하위 quartile |
| **Sell Fill Ratio (평균)** | 100% | 매도는 항상 전량 체결 |
| **Slippage (평균)** | 2.14 bps | 편도 슬리피지 |
| **Slippage (p95)** | 2.14 bps | 거의 일정 |
| **수수료 (Total)** | 9.0 bps | Upbit 5 + Binance 4 |
| **Roundtrip Cost** | 13.28 bps | 2.14*2 + 9.0 |

**핵심 문제:**
- **Buy Fill 26%는 모든 실행에서 고정값**
- 이것은 Fill Model 파라미터가 하드코딩되어 있음을 의미
- `available_volume` 값이 실제 시장 데이터를 반영하지 못함

### D82-12 실행 결과 (logs/d82-11/runs/*.json)

| 후보 | Entry | TP | Buy Fill Ratio | Sell Fill Ratio | Slippage (Buy) | Slippage (Sell) |
|------|-------|-----|----------------|-----------------|----------------|-----------------|
| E10.0/TP12.0 | 10.0 | 12.0 | **0.2615** | 1.0 | 2.136 bps | 2.135 bps |
| E7.0/TP12.0 | 7.0 | 12.0 | **0.2615** | 1.0 | 2.136 bps | 2.135 bps |
| E5.0/TP12.0 | 5.0 | 12.0 | **0.2615** | 1.0 | 2.136 bps | 2.135 bps |

**결론:**
- Entry/TP Threshold와 무관하게 동일한 Fill Ratio
- Fill Model이 시장 조건을 반영하지 않음

---

## 📊 현재 Fill Model의 문제점

### 1️⃣ 고정값 Fill Ratio (26.15%)
**문제:**
- 모든 심볼, 모든 Threshold에서 동일한 값
- `available_volume`이 실제 L1/L2 호가 데이터와 연결되지 않음
- 결과적으로 **74% 거래 기회 차단**

**원인 추정:**
```python
# 추정되는 현재 로직 (간접 추론)
available_volume = 고정값  # 예: 1000 USDT
order_quantity = 3825.96 USDT  # D82-12 평균
fill_ratio = available_volume / order_quantity = 0.2615
```

### 2️⃣ 슬리피지 과대 추정 (2.14 bps)
**문제:**
- D77-4 당시에는 더 낮은 슬리피지였을 가능성
- 현재는 모든 거래에서 2.14 bps로 일정

**비교:**
- D77-4 (추정): 1.0~1.5 bps
- D82-12 (실측): 2.14 bps (40%+ 높음)

### 3️⃣ L2 Orderbook 부재
**문제:**
- 현재는 L1 (Top of Book) 만 사용
- `available_volume`이 실제 호가 잔량과 무관
- AdvancedFillModel의 가상 L2는 실제 데이터 아님

**영향:**
- Fill 가능 여부를 정확히 판단할 수 없음
- Partial Fill 로직이 현실을 반영하지 못함

### 4️⃣ 시장 조건 변화 미반영
**D77-4 (과거):**
- 변동성 높음
- Spread 빈번
- Fill 기회 많음
- Fill Ratio 추정: 50%+ (추정)

**D82-12 (현재):**
- 변동성 낮음
- Spread 희박
- Fill 기회 적음
- Fill Ratio 실측: 26.15%

---

## 🎯 D82 시리즈에서 Fill Model이 미친 영향

### D77-4 vs D82-12 비교

| 항목 | D77-4 (60min) | D82-12 (10min) | 차이 |
|------|---------------|----------------|------|
| **Entry/TP** | 5-10 bps | 5-10 bps | 동일 |
| **Round Trips** | 1,656 | 3 | **99.8% 감소** |
| **RT/min** | 27.6 | 0.3 | **99% 감소** |
| **Fill Ratio (추정)** | 50%+ | 26.15% | **48% 감소** |
| **PnL** | +$8,263.82 | -$5,537.53 | 손익 역전 |

**가설:**
- D77-4는 더 높은 Fill Ratio (50%+) 또는 다른 Fill Model 사용
- 26.15% Fill Model은 D80-4 도입 시점부터 적용됨
- D77-4 → D82 전환 시 Fill Model 변경으로 인한 성능 저하

---

## 🔬 관련 테스트 현황

### Fill Model 관련 테스트

| 테스트 파일 | 테스트 수 | 커버리지 |
|------------|-----------|----------|
| `tests/test_d80_4_fill_model.py` | 15 tests | SimpleFillModel 기본 동작 |
| `tests/test_d81_1_advanced_fill_model.py` | 16 tests | AdvancedFillModel 로직 |
| `tests/test_d80_4_executor_integration.py` | 7 tests | Executor + Fill Model 통합 |
| `tests/test_d81_0_executor_factory_integration.py` | 29 tests | ExecutorFactory + Fill Model |
| `tests/test_d81_1_executor_advanced_fill_integration.py` | 32 tests | AdvancedFillModel 통합 |

**총 테스트:** 99 tests (Fill Model 관련)  
**상태:** 모두 PASS

### 테스트 커버리지

✅ **잘 커버된 영역:**
- Fill Model 계산 로직 (Partial Fill, Slippage)
- ExecutionResult에 Fill 정보 포함
- TradeLogEntry에 Fill 정보 로깅

❌ **커버되지 않은 영역:**
- **실제 시장 데이터 기반 Fill Ratio**
- **Zone별 Fill Ratio 차이**
- **Entry/TP Threshold에 따른 Fill 확률 변화**
- **L2 Orderbook 기반 Fill 판단**

---

## 📝 관련 문서

### D80 시리즈 (Fill Model 도입)
- `docs/D80/D80-4_FILL_MODEL_DESIGN.md`: SimpleFillModel 설계
- `docs/D80/D80-4_FILL_MODEL_TEST_REPORT.md`: 초기 테스트 결과

### D81 시리즈 (Advanced Fill Model)
- `docs/D81/D81-1_ADVANCED_FILL_MODEL.md`: AdvancedFillModel 설계
- `docs/D81/D81-1_INTEGRATION_REPORT.md`: Executor 통합 결과

### D82 시리즈 (Threshold Tuning 실패)
- `docs/D82/D82-9_ANALYSIS.md`: Buy Fill 26% 문제 최초 발견
- `docs/D82/D82-10_RECALIBRATED_EDGE_MODEL.md`: Cost Profile 측정
- `docs/D82/D82-12_VALIDATION_REPORT.md`: Threshold 접근법 실패 확정

---

## 💡 AS-IS 요약 및 D84-0 방향성

### 현재 상태 (AS-IS)
✅ **강점:**
- Fill Model 인프라 완비 (D80-4, D81-1)
- ExecutionResult, TradeLogEntry에 Fill 정보 포함
- 99 tests로 견고한 테스트 커버리지

❌ **약점:**
- **고정값 Fill Ratio (26.15%)** → 74% 기회 차단
- **L2 Orderbook 부재** → Fill 판단 부정확
- **시장 조건 미반영** → D77-4 성능 재현 불가
- **Zone별 Fill 차이 없음** → 모든 Threshold 동일

### D84-0 목표 (TO-BE)
1. **실제 PAPER 데이터 수집**
   - D82-11/12 실행 로그에서 Fill Event 추출
   - Entry/TP Zone별 Fill Ratio 계산

2. **Fill Model v1 보정**
   - 26.15% 고정값 → Zone별 실측값 적용
   - Slippage 2.14 bps → 실측 분포 반영

3. **짧은 PAPER 검증**
   - 10분 스모크 테스트로 Fill Model v1 동작 확인
   - 실측 Fill Ratio가 개선되는지 검증

4. **한계 인식**
   - L2 Orderbook 없이는 근본적 한계 존재
   - D83-x (L2 통합)이 필수 후속 단계

---

**Generated by:** D84-0 AS-IS Analysis  
**Date:** 2025-12-06  
**Next Step:** D84-0 설계 문서 작성
