# D87-1: Fill Model Integration – Advisory Mode

**작성일:** 2025-12-07  
**상태:** ✅ **COMPLETED**  
**버전:** v1.0

## 목표

D87-0에서 정의한 FillModelIntegration 인터페이스를 **Advisory Mode** 수준으로 구현하고, Multi-Exchange Execution 파이프라인(ArbRoute, CrossExchangeExecutor, CrossExchangeRiskGuard)에 통합하여 Zone별 fill_ratio 차이를 실전 트레이딩에 반영한다.

**핵심 원칙:**
- **Conservative Bias:** Zone별 보정은 작고 보수적 (±10% 이내)
- **Config-driven:** 모든 파라미터는 설정으로 조정 가능
- **Backward Compatible:** mode="none" 시 기존 동작과 완전히 동일
- **Safe Integration:** 기존 전략/리스크 구조를 망가뜨리지 않음

---

## 구현 완료 사항

### 1. FillModelIntegration 구현

**파일:** `arbitrage/execution/fill_model_integration.py`

#### 1.1 FillModelConfig 확장

Advisory Mode 파라미터 추가:

```python
@dataclass
class FillModelConfig:
    enabled: bool = False
    mode: Literal["none", "advisory", "strict"] = "none"
    calibration_path: Optional[str] = None
    min_confidence_level: float = 0.5
    staleness_threshold_seconds: float = 86400.0
    
    # Advisory Mode 파라미터 (D87-1)
    advisory_score_bias_z2: float = 5.0          # Z2 Score +5.0
    advisory_score_bias_other: float = -2.0      # Z1/Z3/Z4 Score -2.0
    advisory_size_multiplier_z2: float = 1.1     # Z2 수량 10% 증가
    advisory_size_multiplier_other: float = 1.0  # 기타 Zone 변화 없음
    advisory_risk_multiplier_z2: float = 1.1     # Z2 Risk Limit 10% 완화
    advisory_risk_multiplier_other: float = 1.0  # 기타 Zone 변화 없음
```

#### 1.2 from_config() 구현

Calibration JSON 파일 로드 및 유효성 검증:

```python
@classmethod
def from_config(cls, config: FillModelConfig) -> "FillModelIntegration":
    """
    Config로부터 인스턴스 생성.
    
    - Calibration JSON 로드
    - 필수 필드 검증 (version, zones, default_buy_fill_ratio, ...)
    - FileNotFoundError / ValueError 예외 처리
    """
```

**검증 완료:**
- ✅ D86 Calibration JSON (`logs/d86/d86_0_calibration.json`) 로드 성공
- ✅ 필수 필드 누락 시 ValueError 발생
- ✅ 파일 없음 시 FileNotFoundError 발생

#### 1.3 compute_advice() 구현

Entry/TP Threshold로부터 Zone 선택 및 FillModelAdvice 생성:

```python
def compute_advice(self, entry_bps: float, tp_bps: float) -> Optional[FillModelAdvice]:
    """
    Zone 매칭:
    - Z1: Entry 5-7 bps, TP 7-12 bps → fill_prob=0.2615 (26%)
    - Z2: Entry 7-12 bps, TP 10-20 bps → fill_prob=0.6307 (63%)
    - Z3: Entry 12-20 bps, TP 15-30 bps → fill_prob=0.2615 (26%)
    - Z4: Entry 20-30 bps, TP 25-40 bps → fill_prob=0.2615 (26%)
    - DEFAULT: Zone 미매칭 시 기본값 사용
    
    Confidence Level: samples / 30.0 (30 samples = 100% confidence)
    """
```

**검증 완료:**
- ✅ Z2 Zone 정확히 매칭 (entry=10, tp=15 → Z2)
- ✅ Z1 Zone 정확히 매칭 (entry=6, tp=10 → Z1)
- ✅ Zone 미매칭 시 DEFAULT 사용 (entry=40, tp=50 → DEFAULT)
- ✅ mode="none" 시 None 반환
- ✅ enabled=False 시 None 반환

#### 1.4 adjust_route_score() 구현

Zone별 Route Score 보정 (Advisory Mode):

**수식:**
```
adjusted_score = base_score + bias
where:
  bias = +5.0  (Z2, 기본값)
  bias = -2.0  (Z1/Z3/Z4, 기본값)

clipped to [0.0, 100.0]
```

**예시:**
- Base Score = 60.0, Zone = Z2 → Adjusted = 65.0
- Base Score = 60.0, Zone = Z1 → Adjusted = 58.0
- Base Score = 90.0, Zone = Z2 → Adjusted = 100.0 (clipped)

**검증 완료:**
- ✅ Z2 Score 보정 (+5.0)
- ✅ Z1 Score 보정 (-2.0)
- ✅ 0~100 범위 클리핑
- ✅ mode="none" 시 변경 없음

#### 1.5 adjust_order_size() 구현

Zone별 주문 수량 조정 (Advisory Mode):

**수식:**
```
adjusted_size = base_size * multiplier
where:
  multiplier = 1.1  (Z2, 기본값)
  multiplier = 1.0  (Z1/Z3/Z4, 기본값)
```

**예시:**
- Base Size = 0.01, Zone = Z2 → Adjusted = 0.011 (+10%)
- Base Size = 0.01, Zone = Z1 → Adjusted = 0.01 (변화 없음)

**검증 완료:**
- ✅ Z2 수량 증가 (1.1배)
- ✅ Z1/Z3/Z4 변화 없음 (1.0배)
- ✅ mode="none" 시 변경 없음

#### 1.6 adjust_risk_limit() 구현

Zone별 Risk Limit 조정 (Advisory Mode):

**수식:**
```
adjusted_limit = base_limit * multiplier
where:
  multiplier = 1.1  (Z2, 기본값)
  multiplier = 1.0  (Z1/Z3/Z4, 기본값)
```

**예시:**
- Base Limit = 100,000 KRW, Zone = Z2 → Adjusted = 110,000 KRW (+10%)
- Base Limit = 100,000 KRW, Zone = Z1 → Adjusted = 100,000 KRW (변화 없음)

**검증 완료:**
- ✅ Z2 Limit 완화 (1.1배)
- ✅ Z1/Z3/Z4 변화 없음 (1.0배)
- ✅ mode="none" 시 변경 없음

#### 1.7 check_health() 구현

Calibration 상태 검증 (staleness, confidence):

**검증 항목:**
- Calibration 로드 여부
- Staleness (calibration_age_seconds > staleness_threshold)
- Confidence Level (avg_confidence < min_confidence_level)

**반환:**
```python
{
    "healthy": bool,
    "calibration_age_seconds": float,
    "confidence_level": float,
    "warnings": list[str]
}
```

**검증 완료:**
- ✅ Calibration 정상 로드 시 healthy=True
- ✅ Calibration 없음 시 healthy=False + warning
- ✅ Confidence 낮음 시 healthy=False + warning

---

### 2. Execution Pipeline 통합

#### 2.1 ArbRoute.evaluate()

**파일:** `arbitrage/domain/arb_route.py`

**변경 사항:**
- `__init__()` 시그니처에 `fill_model_integration` 파라미터 추가
- `evaluate()` 내부에서 `fill_model_integration.adjust_route_score()` 호출
- Fill Model Advice 기반 score 보정 적용

**코드:**
```python
# D87-1: Fill Model Advice 반영 (Advisory Mode)
if fill_model_advice and self.fill_model_integration:
    adjusted_score = self.fill_model_integration.adjust_route_score(
        base_score=total_score,
        advice=fill_model_advice
    )
    logger.debug(
        f"[ARB_ROUTE] Fill Model Score 보정: "
        f"base={total_score:.1f} → adjusted={adjusted_score:.1f}, "
        f"zone={fill_model_advice.zone_id}"
    )
    total_score = adjusted_score
```

**효과:**
- Z2 Zone 라우트는 Score가 +5.0 증가 → 선택 확률 상승
- Z1/Z3/Z4 Zone 라우트는 Score가 -2.0 감소 → 선택 확률 하락

#### 2.2 CrossExchangeExecutor._build_order_sizes()

**파일:** `arbitrage/cross_exchange/executor.py`

**변경 사항:**
- `__init__()` 시그니처에 `fill_model_integration` 파라미터 추가
- `_build_order_sizes()` 내부에서 `fill_model_integration.adjust_order_size()` 호출
- Fill Model Advice 기반 notional 조정

**코드:**
```python
# D87-1: Fill Model Advice 기반 주문 수량 조정
if fill_model_advice and self.fill_model_integration:
    adjusted_notional = self.fill_model_integration.adjust_order_size(
        base_size=notional_krw,
        advice=fill_model_advice
    )
    logger.debug(
        f"[CROSS_EXECUTOR] Fill Model Size 조정: "
        f"base={notional_krw:.2f} → adjusted={adjusted_notional:.2f} KRW, "
        f"zone={fill_model_advice.zone_id}"
    )
    notional_krw = adjusted_notional
```

**효과:**
- Z2 Zone 거래는 주문 수량이 10% 증가 → 더 공격적 진입
- Z1/Z3/Z4 Zone 거래는 주문 수량 변화 없음

#### 2.3 CrossExchangeRiskGuard.check_cross_exchange_trade()

**파일:** `arbitrage/cross_exchange/risk_guard.py`

**변경 사항:**
- `__init__()` 시그니처에 `fill_model_integration` 파라미터 추가
- `check_cross_exchange_trade()` 내부에서 `fill_model_integration.adjust_risk_limit()` 호출
- Fill Model Advice 기반 동적 한도 조정 (임시 config 생성)

**코드:**
```python
# D87-1: Fill Model Advice 기반 동적 한도 조정
adjusted_config = self.config
if fill_model_advice and self.fill_model_integration:
    adjusted_max_notional = self.fill_model_integration.adjust_risk_limit(
        base_limit=self.config.max_notional_krw,
        advice=fill_model_advice
    )
    logger.debug(
        f"[CROSS_RISK_GUARD] Fill Model Risk Limit 조정: "
        f"base={self.config.max_notional_krw:.2f} → adjusted={adjusted_max_notional:.2f} KRW, "
        f"zone={fill_model_advice.zone_id}"
    )
    from copy import copy
    adjusted_config = copy(self.config)
    adjusted_config.max_notional_krw = adjusted_max_notional
```

**효과:**
- Z2 Zone 거래는 Risk Limit이 10% 완화 → 더 큰 포지션 허용
- Z1/Z3/Z4 Zone 거래는 Risk Limit 변화 없음

---

## 테스트

### 테스트 파일

1. **`tests/test_d87_0_fill_model_integration_skeleton.py`** (12 tests)
   - D87-0 인터페이스 정의 검증 (D87-1 구현 반영)
   - Backward compatibility 검증 (mode="none")

2. **`tests/test_d87_1_fill_model_integration_advisory.py`** (23 tests)
   - Calibration 로드 검증 (4 tests)
   - Advice 생성 검증 (5 tests)
   - Route Score 조정 검증 (4 tests)
   - Order Size 조정 검증 (3 tests)
   - Risk Limit 조정 검증 (3 tests)
   - Health Check 검증 (3 tests)
   - Integration Summary (1 test)

### 테스트 결과

```
=================== 35 passed in 0.30s ====================
```

**✅ 모든 테스트 통과 (100%)**

### 주요 검증 항목

1. **Calibration 로드**
   - ✅ D86 Calibration JSON 로드 성공
   - ✅ 필수 필드 누락 시 예외 발생
   - ✅ 파일 없음 시 예외 발생

2. **Zone 매칭**
   - ✅ Z2 Zone 정확히 매칭 (entry=10, tp=15)
   - ✅ Z1 Zone 정확히 매칭 (entry=6, tp=10)
   - ✅ Zone 미매칭 시 DEFAULT 사용

3. **Score 조정**
   - ✅ Z2 Score +5.0 보정
   - ✅ Z1 Score -2.0 보정
   - ✅ 0~100 범위 클리핑
   - ✅ mode="none" 시 변경 없음

4. **Size 조정**
   - ✅ Z2 수량 1.1배 증가
   - ✅ Z1/Z3/Z4 변화 없음
   - ✅ mode="none" 시 변경 없음

5. **Limit 조정**
   - ✅ Z2 Limit 1.1배 완화
   - ✅ Z1/Z3/Z4 변화 없음
   - ✅ mode="none" 시 변경 없음

6. **Health Check**
   - ✅ Calibration 정상 로드 시 healthy=True
   - ✅ Calibration 없음 시 healthy=False + warning
   - ✅ Confidence 낮음 시 healthy=False + warning

---

## Advisory Mode 파라미터 권장값

### 기본 설정 (Conservative)

```python
config = FillModelConfig(
    enabled=True,
    mode="advisory",
    calibration_path="logs/d86/d86_0_calibration.json",
    
    # Score Bias (±10% 이내)
    advisory_score_bias_z2=5.0,       # Z2 Score +5.0
    advisory_score_bias_other=-2.0,   # Z1/Z3/Z4 Score -2.0
    
    # Size Multiplier (1.0 ~ 1.2 범위)
    advisory_size_multiplier_z2=1.1,  # Z2 수량 +10%
    advisory_size_multiplier_other=1.0,  # 기타 변화 없음
    
    # Risk Multiplier (1.0 ~ 1.2 범위)
    advisory_risk_multiplier_z2=1.1,  # Z2 Limit +10%
    advisory_risk_multiplier_other=1.0,  # 기타 변화 없음
)
```

### 공격적 설정 (Aggressive)

```python
config = FillModelConfig(
    enabled=True,
    mode="advisory",
    calibration_path="logs/d86/d86_0_calibration.json",
    
    # Score Bias (더 큰 보정)
    advisory_score_bias_z2=10.0,      # Z2 Score +10.0
    advisory_score_bias_other=-5.0,   # Z1/Z3/Z4 Score -5.0
    
    # Size Multiplier (더 큰 증가)
    advisory_size_multiplier_z2=1.2,  # Z2 수량 +20%
    advisory_size_multiplier_other=1.0,
    
    # Risk Multiplier (더 큰 완화)
    advisory_risk_multiplier_z2=1.2,  # Z2 Limit +20%
    advisory_risk_multiplier_other=1.0,
)
```

**⚠️ 주의:**
- 공격적 설정은 PAPER 테스트로 충분히 검증 후 사용
- Z1/Z3/Z4는 항상 보수적 유지 권장

---

## Risk & Limitations

### 1. Calibration Staleness

**문제:**
- Calibration이 오래되면 (24시간+) 현재 시장 상황과 맞지 않을 수 있음

**대응:**
- `check_health()` 메서드로 staleness 확인
- D9x에서 자동 재 calibration 구현 예정

### 2. Zone 미매칭

**문제:**
- Entry/TP가 정의된 Zone 범위 밖이면 DEFAULT 사용
- DEFAULT는 보수적 (fill_prob=0.2615)

**대응:**
- Zone 범위 확대 (D86-2에서 더 많은 데이터 수집)
- Zone 정의 재검토

### 3. Symbol 특성 차이

**문제:**
- D86 Calibration은 BTC/KRW-USDT 기반
- 다른 Symbol에 동일 Calibration 적용 시 부정확할 수 있음

**대응:**
- Symbol별 Calibration 구축 (D9x)
- 현재는 BTC만 사용 권장

### 4. Advisory Mode 한계

**문제:**
- Advisory Mode는 "조언"만 제공, 강제 개입 아님
- Route 선택은 여전히 기존 Score 기반

**대응:**
- D87-2에서 Strict Mode 구현 (Fill Model이 강하게 개입)
- 현재는 Conservative Bias 유지

---

## Acceptance Criteria

### C1. FillModelIntegration 구현

- [x] `from_config()` Calibration 로드 완료
- [x] `compute_advice()` Zone 매칭 및 Advice 생성 완료
- [x] `adjust_route_score()` Score 보정 완료 (Z2 +5.0, Z1/Z3/Z4 -2.0)
- [x] `adjust_order_size()` Size 조정 완료 (Z2 1.1배, Z1/Z3/Z4 1.0배)
- [x] `adjust_risk_limit()` Limit 조정 완료 (Z2 1.1배, Z1/Z3/Z4 1.0배)
- [x] `check_health()` Health Check 완료

### C2. Execution Pipeline 통합

- [x] `ArbRoute.evaluate()` Fill Model Score 보정 통합 완료
- [x] `CrossExchangeExecutor._build_order_sizes()` Size 조정 통합 완료
- [x] `CrossExchangeRiskGuard.check_cross_exchange_trade()` Limit 조정 통합 완료
- [x] mode="none" backward compatibility 유지

### C3. 유닛 테스트

- [x] 35 tests 작성 완료
- [x] 100% PASS (35/35)
- [x] Zone별 보정 검증 완료
- [x] mode="none" backward compatibility 검증 완료

### C4. 문서화

- [x] D87-1 리포트 작성 완료
- [x] Advisory Mode 파라미터 권장값 문서화 완료
- [x] Risk & Limitations 문서화 완료

### C5. Git 상태

- [x] 모든 변경 사항 커밋 준비 완료

---

## 산출물

### 코드

1. **`arbitrage/execution/fill_model_integration.py`** (417 lines)
   - FillModelConfig 확장 (Advisory Mode 파라미터)
   - FillModelIntegration 구현 완료 (7 methods)

2. **`arbitrage/domain/arb_route.py`** (modified)
   - `__init__()` fill_model_integration 파라미터 추가
   - `evaluate()` Score 보정 로직 추가

3. **`arbitrage/cross_exchange/executor.py`** (modified)
   - `__init__()` fill_model_integration 파라미터 추가
   - `_build_order_sizes()` Size 조정 로직 추가

4. **`arbitrage/cross_exchange/risk_guard.py`** (modified)
   - `__init__()` fill_model_integration 파라미터 추가
   - `check_cross_exchange_trade()` Limit 조정 로직 추가

### 테스트

1. **`tests/test_d87_0_fill_model_integration_skeleton.py`** (12 tests)
   - D87-0 인터페이스 검증 (D87-1 구현 반영)

2. **`tests/test_d87_1_fill_model_integration_advisory.py`** (23 tests)
   - Advisory Mode 기능 검증

### 문서

1. **`docs/D87/D87_1_FILL_MODEL_INTEGRATION_ADVISORY_REPORT.md`** (this file)
   - D87-1 구현 상세 리포트
   - Advisory Mode 파라미터 가이드
   - Risk & Limitations

---

## Next Steps

### D87-2: Executor 주문 파라미터 연동 (Strict Mode)

**목표:**
- Strict Mode 구현 (Fill Model이 강하게 개입)
- Zone별 주문 파라미터 더 세밀한 조정
- 20분 PAPER 테스트 (Strict Mode vs Advisory Mode 비교)

**Acceptance Criteria:**
- Strict Mode 구현 완료
- Zone별 파라미터 조정 계수 (수량 ±20%, 가격 오프셋 ±20%)
- 20분 PAPER 테스트 (Strict Mode, Z2 수량 증가 확인)
- A/B 테스트 (Advisory vs Strict Mode 성능 비교)

### D87-3: RiskGuard/Alerting 통합 (Risk-aware Fill Model)

**목표:**
- Fill Model Health Alert 추가 (STALE, LOW_CONFIDENCE, EXTREME_ZONE)
- Zone별 동적 한도 더 세밀한 조정
- 20분 PAPER 테스트 (Risk-aware mode, Z2 포지션 확대 확인)

**Acceptance Criteria:**
- Fill Model Health Alert 구현 완료
- Prometheus 메트릭 추가 (fillmodel_calibration_age_seconds)
- 20분 PAPER 테스트 (Z2 포지션 확대 확인)
- Alert 통합 테스트 (Staleness threshold 초과 시 Alert 발행)

---

## 결론

D87-1에서는 FillModelIntegration을 **Advisory Mode** 수준으로 구현하고, Multi-Exchange Execution 파이프라인에 안전하게 통합했습니다.

**핵심 성과:**
- ✅ Calibration 로드 및 Zone 매칭 구현 완료
- ✅ Z2 Zone 우대 (Score +5.0, Size/Limit +10%)
- ✅ Z1/Z3/Z4 Zone 페널티 (Score -2.0, Size/Limit 변화 없음)
- ✅ mode="none" backward compatibility 완벽 유지
- ✅ 35 tests 100% PASS

**안전성 검증:**
- Conservative Bias (±10% 이내 조정)
- Config-driven (모든 파라미터 설정 가능)
- Backward Compatible (mode="none" 시 기존 동작)
- Safe Integration (기존 구조 유지)

**Next Steps:**
- D87-2: Strict Mode 구현
- D87-3: Risk-aware Fill Model + Alerting
- D9x: Symbol별 Calibration, 자동 재 calibration
