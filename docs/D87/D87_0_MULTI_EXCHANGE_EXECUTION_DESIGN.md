# D87-0: Multi-Exchange Execution Design – Calibrated Fill Model Integration

**작성일:** 2025-12-07  
**상태:** ✅ **DESIGN COMPLETE**

---

## 📋 Overview

### D83~D86 경과 요약

**D83~D85: Real L2 WebSocket + Multi-Exchange Infrastructure**
- ✅ Real L2 WebSocket Provider (Upbit + Binance) 구현 완료
- ✅ Multi-Exchange L2 Aggregation 완료 (D83-3)
- ✅ Multi L2 PAPER 20분/1시간 실행 성공 (D85-1/2)
- ✅ L2 기반 available_volume 동적 계산 (D85-0)

**D86~D86-1: Fill Model Re-Calibration & Validation**
- ✅ FillEventCollector 버그 수정 (entry_bps/tp_bps 올바르게 기록)
- ✅ Zone 재정의: 실측 데이터 기반 4개 Zone (Z1-Z4, Entry 5~30 bps 커버)
- ✅ **핵심 발견: Z2 BUY fill_ratio=0.6307 (63%) vs Z1=0.2615 (26%) → 2.4배 차이**
- ✅ 새 Calibration JSON: `d86_0_calibration.json` (60 events 기반)
- ✅ D86-1 검증 완료: 240 events, Z2 패턴 완벽 재현 (20분 PAPER)

**핵심 통찰:**
- Entry 7-12 bps 구간(Z2)에서 fill_ratio가 다른 구간 대비 2.4배 높음
- D86 Calibration이 재현 가능한 통계적 패턴임을 입증
- SimpleFillModel + CalibratedFillModel 조합이 안정적으로 동작

### D87-0 목표

**High-Level Goal:**
> D83~D86에서 구축한 **Real L2 WebSocket + CalibratedFillModel** 결과를,  
> D75~D80, D77 TopN/Real Market 인프라 위에 있는  
> **Cross-Exchange Executor / ArbRoute / CrossExchangeRiskGuard / Metrics / Alerting** 레이어와  
> 정합성 있게 통합하기 위한 **설계 단계를 완성**한다.

**Why Fill Model for Multi-Exchange Execution?**
1. **슬리피지/체결 리스크 정량화**  
   - Zone별 fill_ratio 차이(26% vs 63%)를 Route 선택에 반영
   - 예상 fill probability로 Route Health Score 보정

2. **Route 선택 최적화 (ArbRoute, RouteHealthScore)**  
   - Z2 고신뢰 구간: 공격적 진입, 포지션 확대
   - Z1/Z3/Z4 저신뢰 구간: 보수적 진입, 포지션 축소

3. **RiskGuard 한도 설정 시 fill probability 반영**  
   - 4-Tier RiskGuard (Exchange → Route → Symbol → Global)에서  
     Zone별 fill_ratio를 고려한 동적 한도 조정

4. **Metrics/Alerting 확장**  
   - Fill Model KPI를 Prometheus/Grafana에 추가
   - Zone별 trade count, fill_ratio, PnL 추적
   - 향후 D86-2/D9x 튜닝 단계에서 피드백 루프 구축

---

## 🏗️ Existing Architecture Recap

### 1. Domain Layer (arbitrage/domain/)

#### ArbRoute (arb_route.py)
**역할:**
- Exchange A ↔ Exchange B 간 라우팅 로직
- RouteScore 계산 (Spread, Health, Fee, Inventory)
- RouteDirection 결정 (LONG_A_SHORT_B / LONG_B_SHORT_A / SKIP)

**핵심 구조:**
```python
@dataclass
class RouteScore:
    spread_score: float  # 0~100
    health_score: float  # 0~100
    fee_score: float     # 0~100
    inventory_penalty: float  # 0~100 (낮을수록 penalty 큼)
    
    def total_score(self) -> float:
        return (
            self.spread_score * 0.4 +
            self.health_score * 0.3 +
            self.fee_score * 0.2 +
            self.inventory_penalty * 0.1
        )
```

**현재 한계:**
- Fill probability / Expected slippage 미반영
- Zone별 차이(Z1 26% vs Z2 63%)를 고려하지 않음

#### ArbUniverse (arb_universe.py)
**역할:**
- Symbol 선택 및 우선순위 관리
- Top-N 심볼 동적 업데이트

#### CrossSync / RiskGuard (cross_sync.py, risk_guard.py)
**역할:**
- 4-Tier RiskGuard (Exchange → Route → Symbol → Global)
- Position 상태 추적 및 한도 검증

### 2. Cross-Exchange Layer (arbitrage/cross_exchange/)

#### CrossExchangeExecutor (executor.py, ~1000 lines)
**역할:**
- Real Upbit/Binance 주문 실행
- Partial fill handling / Rollback logic
- Position state machine 통합 (OPEN → CLOSING → CLOSED)

**핵심 플로우:**
```
CrossExchangeDecision (Paper)
        ↓
CrossExchangeExecutor (Real Orders)
        ↓
├─> Upbit order
├─> Binance order
├─> Fill monitoring
└─> Partial fill handling / Rollback
```

**현재 한계:**
- Fill Model 통합 없음 (always 100% fill assumption)
- Zone별 fill_ratio를 주문 파라미터에 반영 안 함

#### CrossExchangeRiskGuard (risk_guard.py)
**역할:**
- Position limit / PnL threshold 검증
- Consecutive loss tracking
- Multi-currency support (D80-1)

### 3. Execution Layer (arbitrage/execution/)

#### CalibratedFillModel (fill_model.py)
**역할:**
- SimpleFillModel + Zone별 Calibration Ratio 적용
- CalibrationTable.select_zone(entry_bps, tp_bps) → Zone
- Zone별 buy_fill_ratio / sell_fill_ratio 보정

**핵심 구조:**
```python
class CalibratedFillModel(BaseFillModel):
    def __init__(
        self,
        base_model: BaseFillModel,
        calibration: CalibrationTable,
        entry_bps: float = 0.0,
        tp_bps: float = 0.0,
    ):
        self.base_model = base_model
        self.calibration = calibration
        self.entry_bps = entry_bps
        self.tp_bps = tp_bps
        self.zone = calibration.select_zone(entry_bps, tp_bps)
```

**D86 Calibration 결과:**
| Zone | Entry Range | BUY Fill Ratio | Samples |
|------|------------|---------------|---------|
| Z1 | 5-7 bps | 0.2615 (26%) | 24 |
| Z2 | 7-12 bps | **0.6307 (63%)** | 20 |
| Z3 | 12-20 bps | 0.2615 (26%) | 12 |
| Z4 | 20-30 bps | 0.2615 (26%) | 4 |

### 4. Monitoring Layer (arbitrage/monitoring/)

#### CrossExchangeMetrics (cross_exchange_metrics.py)
**역할:**
- RiskGuard decision 기록
- Executor result 기록
- PnL snapshot 기록
- Prometheus export용 인터페이스 제공

**현재 메트릭:**
- `cross_exchange_trades_total`
- `cross_exchange_pnl_krw`
- `cross_exchange_latency_ms`

**확장 필요:**
- `fillmodel_zone_fill_ratio{zone="Z1|Z2|Z3|Z4"}`
- `fillmodel_zone_trade_count{zone="..."}`
- `fillmodel_zone_pnl{zone="..."}`

---

## 🎯 Target Design – Integration Points

### 1. Signal → Route Selection

#### 통합 지점: `ArbRoute.evaluate()`

**현재 동작:**
```python
def evaluate(
    self,
    snapshot: OrderBookSnapshot,
    inventory_imbalance_ratio: float = 0.0,
) -> ArbRouteDecision:
    # Spread Score 계산
    # Health Score 계산
    # Fee Score 계산
    # Inventory Penalty 계산
    # → RouteScore.total_score()
```

**D87-1 확장 목표:**
```python
def evaluate(
    self,
    snapshot: OrderBookSnapshot,
    inventory_imbalance_ratio: float = 0.0,
    fill_model_advice: Optional[FillModelAdvice] = None,  # 新
) -> ArbRouteDecision:
    # 기존 Score 계산 (그대로 유지)
    
    # Fill Model Advice 반영 (新)
    if fill_model_advice:
        fill_probability_adjustment = self._compute_fill_probability_adjustment(
            fill_model_advice
        )
        # total_score에 fill_probability_adjustment 가중치 추가
```

**FillModelAdvice 구조 (D87-1에서 정의 예정):**
```python
@dataclass
class FillModelAdvice:
    """
    Fill Model이 Route Selector에게 제공하는 조언
    
    Attributes:
        entry_bps: Entry threshold (bps)
        tp_bps: TP threshold (bps)
        zone_id: 매칭된 Zone (예: "Z1", "Z2")
        expected_fill_probability: 예상 체결 확률 (0.0 ~ 1.0)
        expected_slippage_bps: 예상 슬리피지 (bps)
        confidence_level: 통계적 신뢰도 (0.0 ~ 1.0, 샘플 수 기반)
    """
    entry_bps: float
    tp_bps: float
    zone_id: str
    expected_fill_probability: float
    expected_slippage_bps: float
    confidence_level: float
```

#### RouteHealthScore 보정 전략

**Zone별 가중치 조정:**
- **Z2 (high fill_ratio=63%)**  
  - total_score += 10 ~ 15 보너스 (공격적 진입 유도)
  - 예: total_score 60 → 70 (threshold 통과 가능성 증가)

- **Z1/Z3/Z4 (low fill_ratio=26%)**  
  - total_score -= 5 ~ 10 패널티 (보수적 진입 유도)
  - 예: total_score 55 → 45 (threshold 미달 가능성 증가)

**구현 방식:**
```python
def _compute_fill_probability_adjustment(
    self,
    fill_model_advice: FillModelAdvice
) -> float:
    """
    Fill probability에 따른 score 조정값 계산
    
    Returns:
        조정값 (-10 ~ +15)
    """
    base_adjustment = (fill_model_advice.expected_fill_probability - 0.5) * 30
    # 예: Z2 (0.63 - 0.5) * 30 = +3.9
    # 예: Z1 (0.26 - 0.5) * 30 = -7.2
    
    # Confidence level로 가중치 조정
    confidence_weight = fill_model_advice.confidence_level
    # 예: Z2 (80 samples) → confidence=0.9, Z4 (20 samples) → confidence=0.5
    
    return base_adjustment * confidence_weight
```

---

### 2. Pre-Trade Risk & Guard

#### 통합 지점: `CrossExchangeRiskGuard.evaluate()`

**현재 동작:**
```python
def evaluate(
    self,
    decision: CrossExchangeDecision,
    position_state: CrossExchangePositionState,
) -> CrossRiskDecision:
    # Position limit 검증
    # PnL threshold 검증
    # Consecutive loss 검증
    # → ALLOW / BLOCK / REDUCE_SIZE
```

**D87-3 확장 목표:**
```python
def evaluate(
    self,
    decision: CrossExchangeDecision,
    position_state: CrossExchangePositionState,
    fill_model_advice: Optional[FillModelAdvice] = None,  # 新
) -> CrossRiskDecision:
    # 기존 검증 (그대로 유지)
    
    # Fill Model 기반 동적 한도 조정 (新)
    if fill_model_advice:
        adjusted_limits = self._adjust_limits_by_fill_probability(
            fill_model_advice
        )
        # Position limit / PnL threshold를 adjusted_limits로 교체
```

#### Zone별 RiskGuard 전략

**Z2 (high fill_ratio=63%)**
- Position limit: 기본 한도 × 1.2 (20% 확대)
- PnL threshold: 기본 threshold × 1.1 (10% 완화)
- 근거: 높은 fill_ratio → 실행 리스크 낮음 → 약간 더 공격적 허용

**Z1/Z3/Z4 (low fill_ratio=26%)**
- Position limit: 기본 한도 × 0.8 (20% 축소)
- PnL threshold: 기본 threshold × 0.9 (10% 엄격화)
- 근거: 낮은 fill_ratio → 실행 리스크 높음 → 보수적 제한

**경고(Alert) 발행 전략:**
```python
def _check_fill_model_health(
    self,
    fill_model_advice: FillModelAdvice
) -> List[Alert]:
    """
    Fill Model 상태 기반 Alert 생성
    
    Returns:
        Alert 리스트
    """
    alerts = []
    
    # 1. Confidence level이 낮은 경우 (샘플 수 부족)
    if fill_model_advice.confidence_level < 0.5:
        alerts.append(Alert(
            severity="WARNING",
            title="FILL_MODEL_LOW_CONFIDENCE",
            message=f"Zone {fill_model_advice.zone_id} confidence={fill_model_advice.confidence_level:.2f} < 0.5"
        ))
    
    # 2. Extreme zone (Z4)에서 fill_ratio 너무 낮은 경우
    if fill_model_advice.zone_id == "Z4" and fill_model_advice.expected_fill_probability < 0.3:
        alerts.append(Alert(
            severity="WARNING",
            title="FILL_MODEL_EXTREME_ZONE_LOW_PROB",
            message=f"Z4 fill_probability={fill_model_advice.expected_fill_probability:.2f} < 0.3"
        ))
    
    return alerts
```

---

### 3. Order Placement & Quote Sizing

#### 통합 지점: `CrossExchangeExecutor._prepare_order_params()`

**현재 동작:**
```python
def _prepare_order_params(
    self,
    decision: CrossExchangeDecision
) -> Tuple[OrderParams, OrderParams]:
    # Upbit/Binance 주문 파라미터 생성 (고정 로직)
    upbit_params = OrderParams(...)
    binance_params = OrderParams(...)
    return upbit_params, binance_params
```

**D87-2 확장 목표:**
```python
def _prepare_order_params(
    self,
    decision: CrossExchangeDecision,
    fill_model_advice: Optional[FillModelAdvice] = None,  # 新
) -> Tuple[OrderParams, OrderParams]:
    # 기존 파라미터 생성 (그대로 유지)
    
    # Fill Model 기반 주문 파라미터 조정 (新)
    if fill_model_advice:
        upbit_params, binance_params = self._adjust_order_params_by_fill_model(
            upbit_params, binance_params, fill_model_advice
        )
    
    return upbit_params, binance_params
```

#### Zone별 주문 파라미터 조정 전략

**Z2 (high fill_ratio=63%)**
- **주문 수량:** 기본 수량 × 1.0 (그대로 유지)
- **가격 오프셋:** 기본 오프셋 × 0.9 (조밀한 주문)
- 근거: 높은 fill_ratio → 호가 레벨에서 체결 확률 높음 → 공격적 가격

**Z1/Z3/Z4 (low fill_ratio=26%)**
- **주문 수량:** 기본 수량 × 0.8 (보수적)
- **가격 오프셋:** 기본 오프셋 × 1.1 (여유있는 주문)
- 근거: 낮은 fill_ratio → 호가 레벨에서 체결 확률 낮음 → 보수적 가격

**수식 예시:**
```python
def _adjust_order_params_by_fill_model(
    self,
    upbit_params: OrderParams,
    binance_params: OrderParams,
    fill_model_advice: FillModelAdvice
) -> Tuple[OrderParams, OrderParams]:
    """
    Fill Model Advice 기반 주문 파라미터 조정
    
    Returns:
        (adjusted_upbit_params, adjusted_binance_params)
    """
    # 기본 조정 계수 계산
    fill_prob = fill_model_advice.expected_fill_probability
    
    # 수량 조정 (fill_prob이 높을수록 유지, 낮을수록 축소)
    qty_factor = 0.8 + 0.4 * fill_prob  # 0.8 ~ 1.2
    # 예: Z2 (0.63) → 1.05, Z1 (0.26) → 0.90
    
    # 가격 오프셋 조정 (fill_prob이 높을수록 공격적, 낮을수록 보수적)
    price_offset_factor = 1.2 - 0.4 * fill_prob  # 0.8 ~ 1.2
    # 예: Z2 (0.63) → 0.95, Z1 (0.26) → 1.10
    
    upbit_params.quantity *= qty_factor
    binance_params.quantity *= qty_factor
    
    upbit_params.price_offset *= price_offset_factor
    binance_params.price_offset *= price_offset_factor
    
    return upbit_params, binance_params
```

---

### 4. Post-Trade Metrics & Feedback Loop

#### 통합 지점: `CrossExchangeMetrics.record_execution()`

**현재 동작:**
```python
def record_execution(
    self,
    result: CrossExecutionResult
):
    # trades_total 증가
    # pnl_krw gauge 업데이트
    # latency_ms histogram 기록
```

**D87-1 확장 목표:**
```python
def record_execution(
    self,
    result: CrossExecutionResult,
    fill_model_advice: Optional[FillModelAdvice] = None,  # 新
):
    # 기존 메트릭 (그대로 유지)
    
    # Fill Model 메트릭 추가 (新)
    if fill_model_advice:
        self._record_fill_model_metrics(result, fill_model_advice)
```

#### 신규 Prometheus 메트릭

**1. fillmodel_zone_fill_ratio (Gauge)**
```python
# HELP fillmodel_zone_fill_ratio Fill ratio by zone
# TYPE fillmodel_zone_fill_ratio gauge
fillmodel_zone_fill_ratio{zone="Z1",side="BUY"} 0.2615
fillmodel_zone_fill_ratio{zone="Z2",side="BUY"} 0.6307
fillmodel_zone_fill_ratio{zone="Z3",side="BUY"} 0.2615
fillmodel_zone_fill_ratio{zone="Z4",side="BUY"} 0.2615
```

**2. fillmodel_zone_trade_count (Counter)**
```python
# HELP fillmodel_zone_trade_count Trade count by zone
# TYPE fillmodel_zone_trade_count counter
fillmodel_zone_trade_count{zone="Z1"} 24
fillmodel_zone_trade_count{zone="Z2"} 20
fillmodel_zone_trade_count{zone="Z3"} 12
fillmodel_zone_trade_count{zone="Z4"} 4
```

**3. fillmodel_zone_pnl (Gauge)**
```python
# HELP fillmodel_zone_pnl PnL by zone (KRW)
# TYPE fillmodel_zone_pnl gauge
fillmodel_zone_pnl{zone="Z1"} 1234.56
fillmodel_zone_pnl{zone="Z2"} 5678.90
fillmodel_zone_pnl{zone="Z3"} -123.45
fillmodel_zone_pnl{zone="Z4"} 789.01
```

**4. fillmodel_calibration_age_seconds (Gauge)**
```python
# HELP fillmodel_calibration_age_seconds Time since last calibration update
# TYPE fillmodel_calibration_age_seconds gauge
fillmodel_calibration_age_seconds 3600  # 1시간 경과
```

#### 피드백 루프 설계 (D9x 향후 단계)

**목표:**
> Fill Model 메트릭을 실시간 수집하여, 향후 D86-2/D9x 단계에서  
> Calibration JSON을 자동으로 재생성하는 피드백 루프 구축

**플로우:**
```
1. CrossExchangeExecutor 실행 중
   ↓
2. FillEventCollector가 fill_events.jsonl에 이벤트 기록
   ↓
3. Prometheus가 fillmodel_zone_* 메트릭 수집
   ↓
4. 일정 기간(예: 24시간) 경과 후
   ↓
5. scripts/recalibrate_fill_model.py 자동 실행
   ↓
6. 새 Calibration JSON 생성 (예: d87_1_calibration.json)
   ↓
7. A/B 테스트: 기존 vs 신규 Calibration 성능 비교
   ↓
8. 성능 향상 시 → 신규 Calibration 활성화
   ↓
9. D_ROADMAP 업데이트 및 git 커밋
```

**Staleness 감지:**
- `fillmodel_calibration_age_seconds > 86400` (24시간 초과)  
  → Alert "FILL_MODEL_STALE" 발행
- 자동 재 calibration 트리거

---

## ⚙️ Config & Runtime Controls

### Config 레벨 Fill Model 제어

**ArbitrageConfig 확장:**
```python
@dataclass
class FillModelConfig:
    """
    Fill Model 설정
    
    D87-1에서 구현 예정
    """
    enabled: bool = False  # Fill Model 활성화 여부
    mode: Literal["none", "advisory", "strict"] = "none"  # 동작 모드
    calibration_path: Optional[str] = None  # Calibration JSON 경로
    min_confidence_level: float = 0.5  # 최소 신뢰도 (샘플 수 기반)
    staleness_threshold_seconds: float = 86400.0  # 24시간
    
    # Zone별 가중치 (D87-1+ 확장)
    zone_weight_z1: float = 1.0
    zone_weight_z2: float = 1.0
    zone_weight_z3: float = 1.0
    zone_weight_z4: float = 1.0

@dataclass
class ArbitrageConfig:
    # ... 기존 필드 ...
    
    # 新
    fill_model: FillModelConfig = field(default_factory=FillModelConfig)
```

### 동작 모드 정의

#### Mode: "none" (기본값)
- Fill Model 완전 비활성화
- 기존 동작과 100% 동일
- 사용 시나리오: Fill Model 없이 안정성 우선 운영

#### Mode: "advisory"
- Fill Model은 모니터링/로그/메트릭에만 반영
- Route 선택, 주문 파라미터, RiskGuard 결정에는 사용 안 함
- 사용 시나리오:
  - Fill Model 초기 도입 단계 (D87-1)
  - 데이터 수집 및 검증 목적
  - A/B 테스트 준비 단계

#### Mode: "strict"
- Executor가 Fill Model에 강하게 의존
- Route Health Score 보정 활성화
- 주문 파라미터 조정 활성화
- RiskGuard 동적 한도 활성화
- 사용 시나리오:
  - Fill Model 검증 완료 후 (D87-2+)
  - 상용 운영 단계 (D87-3+)
  - 높은 신뢰도 Calibration 확보 시

### 런타임 제어

**CLI 인자:**
```bash
python scripts/run_d87_1_multi_exchange_paper.py \
  --fill-model-enabled \
  --fill-model-mode advisory \
  --fill-model-calibration logs/d86/d86_0_calibration.json
```

**환경 변수:**
```bash
export ARBITRAGE_FILL_MODEL_ENABLED=true
export ARBITRAGE_FILL_MODEL_MODE=advisory
export ARBITRAGE_FILL_MODEL_CALIBRATION_PATH=logs/d86/d86_0_calibration.json
```

---

## 🚨 Risk & Failure Modes

### Failure Mode 1: L2 데이터 끊김 → Fill Model Stale

**현상:**
- Real L2 WebSocket 연결 끊김 (Upbit/Binance)
- available_volume 업데이트 없음
- Fill Model이 stale한 데이터로 계산

**방어 전략:**
1. **HealthCheck 강화**
   - `EXCHANGE_HEALTH` Alert (D76 기존)
   - `FILL_MODEL_HEALTH` Alert (新, D87-1)
   - `fillmodel_calibration_age_seconds` 모니터링

2. **Staleness Threshold 초과 시 자동 Fallback**
```python
if calibration_age_seconds > config.staleness_threshold_seconds:
    logger.warning("[FILL_MODEL] Calibration stale, fallback to conservative mode")
    # Fill Model 비활성화
    # SimpleFillModel로 회귀
    # Alert "FILL_MODEL_STALE" 발행
```

3. **WebSocket 재연결 후 자동 재활성화**
```python
if websocket_reconnected and calibration_age_seconds < threshold:
    logger.info("[FILL_MODEL] L2 reconnected, re-enable Fill Model")
    # Fill Model 재활성화
```

### Failure Mode 2: 잘못된 Symbol/Market에 Fill Model 적용

**현상:**
- BTC/USDT Calibration을 ETH/USDT에 잘못 적용
- BTC Upbit vs Binance Calibration을 BTC Upbit vs Bybit에 잘못 적용

**방어 전략:**
1. **Calibration JSON에 심볼/마켓 정보 명시**
```json
{
  "version": "d86_0",
  "symbol": "BTC",
  "markets": ["upbit", "binance"],
  "zones": [...]
}
```

2. **로딩 시 심볼/마켓 검증**
```python
def load_calibration(path: str, expected_symbol: str) -> CalibrationTable:
    data = json.load(open(path))
    
    if data["symbol"] != expected_symbol:
        raise ValueError(
            f"Calibration symbol mismatch: "
            f"expected={expected_symbol}, got={data['symbol']}"
        )
    
    return CalibrationTable(...)
```

3. **Multi-Symbol 지원 시 Symbol별 Calibration 분리**
```
logs/calibrations/
  d86_0_btc_upbit_binance.json
  d87_1_eth_upbit_binance.json
  d87_2_sol_upbit_binance.json
```

### Failure Mode 3: 샘플 수 부족 Zone에서 Fill Model 과신

**현상:**
- Z4 (Entry 20-30 bps): 샘플 수 4개 (D86-1: 20개)
- 통계적 신뢰도 낮음에도 Fill Model을 신뢰

**방어 전략:**
1. **Confidence Level 계산 (샘플 수 기반)**
```python
def compute_confidence_level(samples: int) -> float:
    """
    샘플 수 기반 신뢰도 계산
    
    Returns:
        0.0 ~ 1.0
    """
    if samples < 10:
        return 0.0  # 신뢰도 없음
    elif samples < 30:
        return samples / 30  # 예: 20 samples → 0.67
    else:
        return 1.0  # 충분한 신뢰도
```

2. **Confidence Level < Threshold 시 Fill Model 비활성화**
```python
if fill_model_advice.confidence_level < config.min_confidence_level:
    logger.warning(
        f"[FILL_MODEL] Low confidence zone {fill_model_advice.zone_id}, "
        f"fallback to default"
    )
    # Fill Model Advice 무시
    # 기본 정책으로 회귀
```

3. **Alert 발행**
```python
if fill_model_advice.confidence_level < 0.5:
    alerting.send_alert(Alert(
        severity="WARNING",
        title="FILL_MODEL_LOW_CONFIDENCE",
        message=f"Zone {fill_model_advice.zone_id} samples={samples} < 30"
    ))
```

---

## 🛣️ Roadmap: D87-x Sub-Steps

### D87-1: CalibratedFillModel → RouteHealthScore 연동 (Advisory Mode)

**목표:**
- ArbRoute.evaluate()에 FillModelAdvice 주입
- RouteHealthScore에 fill_probability_adjustment 추가
- Advisory Mode 구현 (메트릭/로그만 반영)

**Done Criteria:**
1. ✅ FillModelAdvice 데이터 클래스 정의
2. ✅ ArbRoute.evaluate() 시그니처 확장 (backward compat)
3. ✅ RouteHealthScore 보정 로직 구현
4. ✅ Advisory Mode 활성화 시 로그/메트릭 기록
5. ✅ 유닛 테스트: 10+ tests (Zone별 score 보정 검증)
6. ✅ 5분 PAPER 테스트: Advisory Mode, fill_model_* 메트릭 확인
7. ✅ 문서화: D87-1 리포트

**리스크:**
- RouteHealthScore 변경으로 인한 기존 동작 영향
- 완화: backward compatibility 보장 (fill_model_advice=None 시 기존 동작)

---

### D87-2: CalibratedFillModel → CrossExchangeExecutor 주문 파라미터 연동 (Strict Mode)

**목표:**
- CrossExchangeExecutor._prepare_order_params()에 FillModelAdvice 주입
- Zone별 주문 수량/가격 오프셋 조정 구현
- Strict Mode 구현 (실제 주문 파라미터 변경)

**Done Criteria:**
1. ✅ CrossExchangeExecutor._prepare_order_params() 시그니처 확장
2. ✅ Zone별 주문 파라미터 조정 로직 구현
3. ✅ Strict Mode 활성화 시 실제 주문 변경
4. ✅ 유닛 테스트: 10+ tests (Zone별 파라미터 변경 검증)
5. ✅ 20분 PAPER 테스트: Strict Mode, Z2 수량 증가 확인
6. ✅ A/B 테스트: Advisory vs Strict Mode 성능 비교
7. ✅ 문서화: D87-2 리포트

**리스크:**
- 주문 파라미터 변경으로 인한 체결 실패 증가
- 완화: 초기 조정 계수 보수적 설정 (±10% 이내)

---

### D87-3: CrossExchangeRiskGuard/Alerting 통합 (Risk-aware Fill Model)

**목표:**
- CrossExchangeRiskGuard.evaluate()에 FillModelAdvice 주입
- Zone별 동적 한도 조정 (Position limit / PnL threshold)
- Fill Model Health Alert 추가

**Done Criteria:**
1. ✅ CrossExchangeRiskGuard.evaluate() 시그니처 확장
2. ✅ Zone별 동적 한도 조정 로직 구현
3. ✅ Fill Model Health Alert (STALE, LOW_CONFIDENCE 등)
4. ✅ 유닛 테스트: 10+ tests (Zone별 한도 조정 검증)
5. ✅ 20분 PAPER 테스트: Risk-aware mode, Z2 포지션 확대 확인
6. ✅ Alert 통합 테스트: Staleness threshold 초과 시 Alert 발행
7. ✅ 문서화: D87-3 리포트

**리스크:**
- RiskGuard 한도 완화로 인한 손실 확대
- 완화: Z2 한도 확대 비율 제한 (최대 +20%)

---

### D87-4: Long PAPER 검증 + 실거래 대비 Fill Model 정확도 분석 (Optional)

**목표:**
- 1시간 PAPER 실행 (D87-3 기반)
- 500+ Fill Events 수집
- Fill Model 예측 vs 실제 체결 비교 분석

**Done Criteria:**
1. ✅ 1시간 PAPER 실행 (Strict Mode + Risk-aware)
2. ✅ 500+ Fill Events 수집
3. ✅ Fill Model 예측 정확도 분석 (MAE, RMSE)
4. ✅ Zone별 실제 fill_ratio vs 예측 fill_ratio 비교
5. ✅ D87-4 리포트: 정확도 분석, 개선 방향 제시
6. ✅ D86-2 (1시간 PAPER) 결과와 비교

**리스크:**
- 장기 실행 중 L2 WebSocket 끊김
- 완화: 자동 재연결 + HealthCheck 강화 (D83-1 기반)

---

## 📚 Appendix – D86 결과 정리 & 참조 링크

### D86/D86-1 핵심 수치 요약

**D86 (5분 Smoke Test):**
- Session ID: 20251207_120533
- Duration: 305.5초 (5.1분)
- Fill Events: 60 (BUY 30, SELL 30)
- Zone 분포: Z1=24, Z2=20, Z3=12, Z4=4

**D86-1 (20분 PAPER Validation):**
- Session ID: 20251207_123906
- Duration: 1205.9초 (20.1분)
- Fill Events: 240 (BUY 120, SELL 120)
- Zone 분포: Z1=80, Z2=80, Z3=60, Z4=20

**Zone별 Fill Ratio (D86 vs D86-1):**
| Zone | Entry Range | D86 BUY Fill Ratio | D86-1 BUY Fill Ratio | 변화 |
|------|------------|-------------------|---------------------|------|
| Z1 | 5-7 bps | 0.2615 (26%) | 0.2615 (26%) | **동일** ✅ |
| Z2 | 7-12 bps | **0.6307 (63%)** | **0.6307 (63%)** | **동일** ✅ |
| Z3 | 12-20 bps | 0.2615 (26%) | 0.2615 (26%) | **동일** ✅ |
| Z4 | 20-30 bps | 0.2615 (26%) | 0.2615 (26%) | **동일** ✅ |

**핵심 발견:**
- ✅ Z2의 높은 fill_ratio (63%)가 재현 가능한 패턴임을 입증
- ✅ D86 Calibration(d86_0_calibration.json)이 실전에서 유효
- ✅ SimpleFillModel + CalibratedFillModel 조합이 안정적으로 동작

### 관련 파일 링크

**문서:**
- `docs/D86/D86_FILL_MODEL_RECALIBRATION_REPORT.md`
- `docs/D86/D86-1_FILL_MODEL_20M_PAPER_VALIDATION_REPORT.md`

**Calibration JSON:**
- `logs/d86/d86_0_calibration.json` (D86, 60 events)
- `logs/d86-1/calibration_20251207_123906.json` (D86-1, 240 events)

**Fill Events:**
- `logs/d86/fill_events_20251207_120533.jsonl` (D86, 60 events)
- `logs/d86-1/fill_events_20251207_123906.jsonl` (D86-1, 240 events)

**KPI:**
- `logs/d86-1/kpi_20251207_123906.json`

**분석 도구:**
- `scripts/analyze_d86_fill_data.py` (CLI 인자 추가)

**테스트:**
- `tests/test_d86_fill_calibration.py` (8 tests, 100% PASS)
- `tests/test_d84_1_calibrated_fill_model.py` (10 tests, 100% PASS)

---

## ✅ Design Complete

이 문서는 D87-0의 설계 단계를 완성하며, 다음 단계인 D87-1~D87-3에서  
실제 구현을 어디에 어떻게 넣을지 명확하게 정의한다.

**Next Steps:**
- D87-1: RouteHealthScore 연동 (Advisory Mode) - 코드 + 유닛 테스트
- D87-2: Executor 주문 파라미터 연동 (Strict Mode) - PAPER 검증
- D87-3: RiskGuard/Alerting 통합 - Risk-aware Fill Model
- (Optional) D87-4: Long PAPER 검증 + 정확도 분석

---

**작성자:** arbitrage-lite project  
**마지막 업데이트:** 2025-12-07
