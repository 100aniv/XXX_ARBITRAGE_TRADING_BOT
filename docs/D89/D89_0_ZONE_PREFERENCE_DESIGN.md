# D89-0: Zone Preference Weight Tuning & Design

**작성일:** 2025-12-09  
**목적:** Zone Preference 가중치를 강화하여 Advisory vs Strict 간 Zone 분포 차이(ΔP(Z2))를 3%p 이상으로 확대

---

## 0. 배경

### D88-2 결과 요약
- **목표:** Entry BPS random 모드에서 Advisory vs Strict A/B 테스트로 Zone Preference 효과 검증
- **실행:** Advisory 30m, Strict 30m (각 180 trades, 360 fill events)
- **결과:**
  - Advisory Z2: 27.8%
  - Strict Z2: 25.6%
  - **ΔP(Z2) = 2.2%p** (목표: ≥3%p 미달)
- **판정:** ⚠️ CONDITIONAL PASS (Zone Preference 로직 작동하나 효과 미미)

### 문제 정의
1. **Entry BPS 분포 지배 문제**
   - Random 모드(5.0~25.0 bps 균일 분포)로 인해 Entry BPS가 Zone을 강하게 결정
   - Zone Preference (현재 Advisory Z2=1.05, Strict Z2=1.15)의 영향력이 제한됨

2. **가중치 부족**
   - Advisory Z2=1.05 (5% 증가)로는 통계적으로 유의미한 차이를 만들지 못함
   - Multiplicative 방식: `adjusted_score = base_score * zone_pref`
   - 예: base_score=70 → Advisory: 70*1.05=73.5 (+3.5점, +5%)
   - 이 정도 차이로는 Route 우선순위가 크게 바뀌지 않음

3. **샘플 사이즈 제한**
   - 30분 실행 → 180 trades → Zone별 약 22~66개
   - 통계적 유의성 확보 어려움

---

## 1. AS-IS: 현재 Zone Preference 구조

### 1.1 코드 위치
- **파일:** `arbitrage/execution/fill_model_integration.py`
- **클래스:** `FillModelConfig`, `FillModelIntegration`
- **함수:** `adjust_route_score()` (Line 304~357)

### 1.2 현재 Zone Preference 가중치

**FillModelConfig.__post_init__() (Line 121~144)**
```python
self.zone_preference = {
    "none": {
        "Z1": 1.0,
        "Z2": 1.0,
        "Z3": 1.0,
        "Z4": 1.0,
        "DEFAULT": 1.0,
    },
    "advisory": {
        "Z1": 0.90,  # -10%
        "Z2": 1.05,  # +5%
        "Z3": 0.95,  # -5%
        "Z4": 0.90,  # -10%
        "DEFAULT": 0.95,
    },
    "strict": {
        "Z1": 0.80,  # -20%
        "Z2": 1.15,  # +15%
        "Z3": 0.85,  # -15%
        "Z4": 0.80,  # -20%
        "DEFAULT": 0.85,
    },
}
```

### 1.3 Score 조정 로직

**adjust_route_score() (Line 334~357)**
```python
zone_pref = self.config.zone_preference.get(self.config.mode, {}).get(
    zone_id,
    self.config.zone_preference[self.config.mode].get("DEFAULT", 1.0)
)

# Multiplicative adjustment
adjusted_score = base_score * zone_pref

# 0~100 범위로 clipping
adjusted_score = max(0.0, min(100.0, adjusted_score))
```

**예시:**
- base_score = 70
- Advisory Z2: 70 * 1.05 = 73.5 (+3.5점, +5%)
- Strict Z2: 70 * 1.15 = 80.5 (+10.5점, +15%)
- Advisory Z1: 70 * 0.90 = 63.0 (-7.0점, -10%)

### 1.4 Advisory vs Strict 차이
- **Advisory:** Z2 약간 선호 (1.05x), Z1/Z4 약간 회피 (0.90x)
- **Strict:** Z2 강하게 선호 (1.15x), Z1/Z4 강하게 회피 (0.80x)
- **문제:** Advisory의 Z2 선호도(1.05x)가 너무 약함

---

## 2. TO-BE: Zone Preference 강화 설계

### 2.1 목표
- **Primary:** ΔP(Z2) ≥ 3.0%p 달성 (Advisory vs Strict)
- **Secondary:** 인프라 기준 유지 (Duration, Fill Events, Unmatched, Fatal Error)
- **Constraint:** Z2 편중 < 60% (Advisory 기준, 극단적 쏠림 방지)

### 2.2 Zone Preference 가중치 재설계

#### 2.2.1 설계 원칙
1. **Advisory만 강화, Strict는 기준선 유지**
   - Strict: 현재 가중치 그대로 (Z2=1.15, Z1/Z4=0.80)
   - Advisory: Z2 가중치를 크게 상향

2. **Multiplicative 방식 유지**
   - 기존 Score 조정 로직(`base_score * zone_pref`) 변경 없음
   - 가중치 값만 변경

3. **극단값 회피**
   - Z2가 80~90%로 쏠리지 않도록 상한선 설정
   - 목표: Advisory Z2 = 40~50% 정도 (현재 27.8%에서 +15%p 정도 증가)

#### 2.2.2 제안 가중치 (초안)

**Option 1: Conservative (Z2 = 2.0x)**
```python
"advisory": {
    "Z1": 0.85,  # -15%
    "Z2": 2.00,  # +100% (기존 1.05 → 2.00)
    "Z3": 0.90,  # -10%
    "Z4": 0.85,  # -15%
    "DEFAULT": 0.90,
}
```
- **예상 효과:** base_score=70 → Z2: 140 (clipped to 100), Z1: 59.5
- **예상 Z2 비율:** 35~45% (현재 27.8%에서 +10%p 정도)
- **예상 ΔP(Z2):** 약 10~15%p (Strict 25.6%와 비교)

**Option 2: Moderate (Z2 = 3.0x) ⭐ 권장**
```python
"advisory": {
    "Z1": 0.80,  # -20%
    "Z2": 3.00,  # +200% (기존 1.05 → 3.00)
    "Z3": 0.85,  # -15%
    "Z4": 0.80,  # -20%
    "DEFAULT": 0.85,
}
```
- **예상 효과:** base_score=70 → Z2: 210 (clipped to 100), Z1: 56
- **예상 Z2 비율:** 45~55% (현재 27.8%에서 +20%p 정도)
- **예상 ΔP(Z2):** 약 20~25%p (Strict 25.6%와 비교)
- **장점:** 명확한 차이 발생, ΔP(Z2) ≥ 3%p 목표 확실히 달성
- **단점:** Z2 쏠림이 다소 강함 (하지만 60% 미만이므로 허용 범위)

**Option 3: Aggressive (Z2 = 4.0x)**
```python
"advisory": {
    "Z1": 0.75,  # -25%
    "Z2": 4.00,  # +300% (기존 1.05 → 4.00)
    "Z3": 0.80,  # -20%
    "Z4": 0.75,  # -25%
    "DEFAULT": 0.80,
}
```
- **예상 효과:** base_score=70 → Z2: 280 (clipped to 100), Z1: 52.5
- **예상 Z2 비율:** 55~65%
- **예상 ΔP(Z2):** 약 30~35%p
- **위험:** Z2 쏠림이 너무 강함, 비정상적 동작 가능성

#### 2.2.3 최종 선택: Option 2 (Z2 = 3.0x)
- **근거:**
  - D88-2에서 Advisory Z2=27.8%, Strict Z2=25.6% (ΔP=2.2%p)
  - Z2 가중치를 1.05 → 3.00으로 약 3배 증가
  - Score 차이: +5% → +200% (40배 증가)
  - 예상 효과: Advisory Z2 비율 45~55%, ΔP(Z2) 약 20~25%p
  - 목표(≥3%p) 달성 확실, 극단적 쏠림(>60%) 회피

### 2.3 파라미터화 방식

#### 2.3.1 기존 방식 유지 (Hard-coded in FillModelConfig)
- **장점:** 단순, 빠른 구현, 기존 코드 변경 최소
- **단점:** 가중치 변경 시 코드 수정 필요
- **결정:** **D89-0에서는 이 방식 사용** (신속한 검증 우선)

#### 2.3.2 YAML 설정 파일 (Future Work)
- **위치:** `config/arbitrage/zone_preference.yaml`
- **형식:**
  ```yaml
  modes:
    none:
      Z1: 1.0
      Z2: 1.0
      Z3: 1.0
      Z4: 1.0
    advisory:
      Z1: 0.80
      Z2: 3.00
      Z3: 0.85
      Z4: 0.80
    strict:
      Z1: 0.80
      Z2: 1.15
      Z3: 0.85
      Z4: 0.80
  ```
- **장점:** 코드 수정 없이 가중치 튜닝 가능, 버전 관리 용이
- **단점:** 파일 I/O 추가, 설정 로더 구현 필요
- **결정:** **D89-1 이후로 미룸** (D89-0은 신속 검증에 집중)

---

## 3. 구현 계획

### 3.1 변경 파일
- **arbitrage/execution/fill_model_integration.py**
  - `FillModelConfig.__post_init__()` (Line 121~144)
  - Advisory mode의 zone_preference 가중치만 변경

### 3.2 변경 내용 (Diff)

**Before (D88-2):**
```python
"advisory": {
    "Z1": 0.90,
    "Z2": 1.05,
    "Z3": 0.95,
    "Z4": 0.90,
    "DEFAULT": 0.95,
},
```

**After (D89-0):**
```python
"advisory": {
    "Z1": 0.80,
    "Z2": 3.00,  # 1.05 → 3.00 (약 3배 증가)
    "Z3": 0.85,
    "Z4": 0.80,
    "DEFAULT": 0.85,
},
```

### 3.3 Strict Mode는 변경 없음
```python
"strict": {
    "Z1": 0.80,
    "Z2": 1.15,  # 그대로 유지 (기준선)
    "Z3": 0.85,
    "Z4": 0.80,
    "DEFAULT": 0.85,
},
```

---

## 4. 검증 계획

### 4.1 Unit Test
- **파일:** `tests/test_d89_0_zone_preference.py`
- **테스트 시나리오:**
  1. **T1: Advisory vs Strict Score 비교**
     - 동일한 base_score에 대해
     - Advisory Z2 Score >> Strict Z2 Score
     - Advisory Z1 Score ≈ Strict Z1 Score (둘 다 0.80)
  
  2. **T2: 설정값 반영 검증**
     - FillModelConfig 생성 시 zone_preference 값 확인
     - Advisory Z2 = 3.00, Strict Z2 = 1.15
  
  3. **T3: Score Clipping 검증**
     - base_score=70, Z2=3.00 → adjusted_score=210 → clipped to 100
     - 0~100 범위 내 clipping 정상 작동

### 4.2 30m A/B Validation
- **설정:** D88-2와 동일
  - Duration: Advisory 30m, Strict 30m
  - Entry BPS Mode: random (5.0~25.0 bps)
  - Entry BPS Seed: Advisory=42, Strict=999
  - Calibration: logs/d86-1/calibration_20251207_123906.json

- **예상 결과:**
  - Advisory Z2: 45~55% (기존 27.8%에서 +20%p 증가)
  - Strict Z2: 25~28% (기존 25.6%와 유사)
  - **ΔP(Z2): 20~25%p** (목표 ≥3%p 달성)

- **Acceptance Criteria:**
  - **C1~C6 (기존 인프라):** 모두 PASS 유지
  - **C7 (NEW): |ΔP(Z2)| ≥ 3.0%p** → PASS (예상 20~25%p)
  - **C8 (Secondary): Advisory Z2 < 60%** → PASS (예상 45~55%)

---

## 5. 위험 요소 및 대응

### 5.1 Z2 과도한 쏠림 (Advisory Z2 > 60%)
- **위험:** Z2 비율이 60% 이상으로 쏠려 비정상적 동작
- **대응:** 
  - 30m 테스트에서 Z2 비율 모니터링
  - 60% 초과 시 가중치를 3.00 → 2.50으로 하향 조정 후 재실행

### 5.2 Strict Mode 영향
- **위험:** Strict 가중치를 건드리지 않았는데도 결과 변경
- **대응:**
  - Strict 테스트 독립 실행하여 D88-2 결과와 비교
  - Z2 비율 차이 < ±2%p 이내여야 함

### 5.3 인프라 기준 저하 (Duration, Fatal Error 등)
- **위험:** 가중치 변경으로 인한 예상치 못한 부작용
- **대응:**
  - 30m 테스트에서 C1~C6 모두 PASS 확인
  - FAIL 발생 시 즉시 중단 및 원인 분석

---

## 6. Next Steps (D89-1 이후)

### 6.1 3h LONGRUN (샘플 사이즈 증가)
- **목적:** 통계적 유의성 확보
- **설정:** Advisory 3h, Strict 3h (각 1000+ trades)
- **기대 효과:** ΔP(Z2) 분산 감소, 더 안정적인 검증

### 6.2 YAML 설정 파일 구현
- **목적:** 가중치 tuning 용이성 향상
- **구현:** config/arbitrage/zone_preference.yaml
- **효과:** 코드 수정 없이 가중치 조정 가능

### 6.3 Fill Size 분석
- **목적:** C8 (ΔFillSize(Z2) ≥ 3%p) 검증
- **구현:** d88_0_analyze_zone_distribution.py 확장
- **효과:** Zone Preference가 Fill Size에도 영향을 주는지 확인

---

## 7. 요약

### AS-IS (D88-2)
- Advisory Z2: 1.05 (5% 증가)
- Strict Z2: 1.15 (15% 증가)
- 결과: ΔP(Z2) = 2.2%p (미달)

### TO-BE (D89-0)
- **Advisory Z2: 3.00 (200% 증가)** ⭐
- Strict Z2: 1.15 (변경 없음)
- 예상: ΔP(Z2) = 20~25%p (목표 달성)

### 변경 범위
- **파일:** arbitrage/execution/fill_model_integration.py (1개)
- **라인:** 131 (Z2 가중치 1.05 → 3.00)
- **테스트:** tests/test_d89_0_zone_preference.py (신규)
- **검증:** 30m A/B Validation (Advisory + Strict)

---

**작성:** Windsurf AI (D89-0 Design Phase)  
**승인 대기:** GPT-5.1 (Final Review & Decision)
